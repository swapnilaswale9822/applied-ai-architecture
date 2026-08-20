"""Circuit breaker keyed on rolling error rate.

Three design decisions that separate a working breaker from a decorative one:

**Rolling error rate, not consecutive failures.** A dependency failing 40% of calls is
broken, but it will rarely produce five consecutive failures — a consecutive-count breaker
never trips on the most common real degradation. This one trips on the rate inside a time
window, with a minimum call count so a single early failure cannot open the circuit on
thin traffic.

**Half-open admits exactly one probe.** The naive implementation lets every waiting caller
through the moment the timer expires, which re-floods a service that is still recovering.
Here exactly one call is admitted; everyone else keeps getting rejected until it reports back.

**Per dependency, never global.** A shared breaker means one provider's outage stops calls
to a healthy one. Breakers are namespaced by dependency in ``CircuitBreakerRegistry``.
"""

import threading
import time
from collections import deque
from typing import Callable, Deque, Optional, Tuple, TypeVar

from .errors import CircuitOpen, PermanentError, RetryableError

T = TypeVar("T")

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        error_rate_threshold: float = 0.5,
        window_seconds: float = 30.0,
        min_calls: int = 10,
        recovery_timeout: float = 15.0,
        clock: Optional[Callable[[], float]] = None,
    ):
        if not 0.0 < error_rate_threshold <= 1.0:
            raise ValueError("error_rate_threshold must be in (0, 1]")
        self.name = name
        self.error_rate_threshold = error_rate_threshold
        self.window_seconds = window_seconds
        self.min_calls = min_calls
        self.recovery_timeout = recovery_timeout
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._outcomes: Deque[Tuple[float, bool]] = deque()  # (at, ok)
        self._state = CLOSED
        self._opened_at = 0.0
        self._probe_in_flight = False

    # ---- introspection -------------------------------------------------

    @property
    def state(self) -> str:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def error_rate(self) -> float:
        with self._lock:
            self._evict()
            if not self._outcomes:
                return 0.0
            failures = sum(1 for _, ok in self._outcomes if not ok)
            return failures / len(self._outcomes)

    # ---- the guard -----------------------------------------------------

    def call(self, fn: Callable[[], T]) -> T:
        """Run ``fn`` through the breaker.

        ``PermanentError`` is deliberately **not** counted as a circuit failure: a 400 means
        the caller sent something wrong, not that the dependency is unhealthy. Counting
        client errors against the breaker lets one bad caller open the circuit for everyone.
        """
        self._before()
        try:
            result = fn()
        except PermanentError:
            self._release_probe()
            raise
        except BaseException:
            self._record(ok=False)
            raise
        self._record(ok=True)
        return result

    def _before(self) -> None:
        with self._lock:
            self._maybe_half_open()
            if self._state == OPEN:
                raise CircuitOpen(self.name, self._retry_after())
            if self._state == HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitOpen(self.name, self._retry_after())
                self._probe_in_flight = True  # this caller is the single probe

    def _record(self, ok: bool) -> None:
        with self._lock:
            now = self._clock()
            if self._state == HALF_OPEN:
                self._probe_in_flight = False
                if ok:
                    self._close()
                else:
                    self._open(now)
                return

            self._outcomes.append((now, ok))
            self._evict()
            if not ok and self._should_trip():
                self._open(now)

    def _release_probe(self) -> None:
        """A permanent error tells us nothing about health — free the probe slot."""
        with self._lock:
            self._probe_in_flight = False

    # ---- state transitions ---------------------------------------------

    def _should_trip(self) -> bool:
        if len(self._outcomes) < self.min_calls:
            return False
        failures = sum(1 for _, ok in self._outcomes if not ok)
        return failures / len(self._outcomes) >= self.error_rate_threshold

    def _open(self, now: float) -> None:
        self._state = OPEN
        self._opened_at = now
        self._probe_in_flight = False
        self._outcomes.clear()

    def _close(self) -> None:
        self._state = CLOSED
        self._probe_in_flight = False
        self._outcomes.clear()

    def _maybe_half_open(self) -> None:
        if self._state == OPEN and self._clock() - self._opened_at >= self.recovery_timeout:
            self._state = HALF_OPEN
            self._probe_in_flight = False

    def _retry_after(self) -> float:
        return max(0.0, self.recovery_timeout - (self._clock() - self._opened_at))

    def _evict(self) -> None:
        cutoff = self._clock() - self.window_seconds
        while self._outcomes and self._outcomes[0][0] < cutoff:
            self._outcomes.popleft()


class CircuitBreakerRegistry:
    """One breaker per dependency. Isolation is the point — never share one."""

    def __init__(self, **defaults):
        self._defaults = defaults
        self._breakers = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> CircuitBreaker:
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, **self._defaults)
            return self._breakers[name]

    def states(self):
        with self._lock:
            return {n: b.state for n, b in self._breakers.items()}
