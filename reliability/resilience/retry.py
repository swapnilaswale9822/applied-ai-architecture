"""Retry with exponential backoff and full jitter.

Two decisions matter more than the retry loop itself:

**Full jitter, not fixed backoff.** When a provider recovers from an outage, every client
that backed off by the same fixed schedule retries in the same instant and knocks it over
again. Randomising the whole interval spreads the recovery. This is AWS's "full jitter":
``sleep = random(0, min(cap, base * 2**attempt))``.

**Only retryable errors.** A ``PermanentError`` is raised immediately. Retrying a schema
violation three times costs three times as much to fail identically.

For LLM calls specifically: retries are not free and not idempotent. At temperature > 0 the
second attempt can return a *different* answer, so the natural pairing is retry-on-
validation-failure — see ``examples.py``.
"""

import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

from .budget import Deadline
from .errors import DeadlineExceeded, PermanentError, RetryableError

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.2
    max_delay: float = 10.0
    #: Full jitter by default. Set False only to make a test deterministic.
    jitter: bool = True

    def delay_for(self, attempt: int, rng: Optional[random.Random] = None) -> float:
        """Backoff before ``attempt`` (1-indexed: the wait before attempt 2 is ``attempt=1``)."""
        capped = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        if not self.jitter:
            return capped
        return (rng or random).uniform(0.0, capped)


def retry_call(
    fn: Callable[[], T],
    policy: Optional[RetryPolicy] = None,
    deadline: Optional[Deadline] = None,
    sleep: Optional[Callable[[float], None]] = None,
    rng: Optional[random.Random] = None,
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> T:
    """Call ``fn`` with bounded retries.

    ``sleep`` and ``rng`` are injectable so tests run instantly and deterministically
    instead of actually waiting — the same seam that makes backoff testable at all.
    """
    policy = policy or RetryPolicy()
    sleep = sleep or time.sleep
    last: BaseException

    for attempt in range(1, policy.max_attempts + 1):
        if deadline:
            deadline.check(f"attempt {attempt}")
        try:
            return fn()
        except PermanentError:
            raise  # never retry: the answer will not change
        except RetryableError as exc:
            last = exc
            if attempt == policy.max_attempts:
                break
            delay = policy.delay_for(attempt, rng)
            # Don't sleep past the deadline just to fail on the next check.
            if deadline and delay >= deadline.remaining():
                raise DeadlineExceeded(
                    f"backoff {delay:.2f}s exceeds remaining budget "
                    f"{deadline.remaining():.2f}s"
                ) from exc
            if on_retry:
                on_retry(attempt, exc, delay)
            sleep(delay)

    raise last
