"""Graceful degradation: a chain of increasingly cheap answers.

The failure mode this prevents is a 500. When the primary model is unavailable, a system
that returns nothing is strictly worse than one that returns a cached answer, a weaker
model's answer, or an honest "I can't answer that right now."

The last tier is deliberately an **explicit refusal, not an exception**. A system that has
run out of options should say so in its own voice — silently guessing is the actual bug.

Every result carries which tier served it, so degradation is visible in traces and metrics
rather than being invisible until someone notices quality dropped.
"""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from .errors import PermanentError


@dataclass
class Attempt:
    tier: str
    error: BaseException


@dataclass
class Outcome:
    value: Any
    tier: str
    #: Tiers that were tried and failed, in order. Empty when the primary served.
    degraded_from: List[Attempt]

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_from)


class FallbackChain:
    """Try handlers in order; the first success wins.

    ``PermanentError`` short-circuits the whole chain: if the request itself is malformed,
    the cheaper model will reject it too. Falling back on a client error just burns every
    tier to produce the same failure.
    """

    def __init__(self, tiers: Optional[List[Tuple[str, Callable[[], Any]]]] = None):
        self._tiers: List[Tuple[str, Callable[[], Any]]] = list(tiers or [])

    def tier(self, name: str, handler: Callable[[], Any]) -> "FallbackChain":
        self._tiers.append((name, handler))
        return self

    def run(self, on_degrade: Optional[Callable[[str, BaseException], None]] = None) -> Outcome:
        if not self._tiers:
            raise ValueError("fallback chain has no tiers")
        failures: List[Attempt] = []
        for name, handler in self._tiers:
            try:
                return Outcome(value=handler(), tier=name, degraded_from=failures)
            except PermanentError:
                raise
            except BaseException as exc:
                failures.append(Attempt(tier=name, error=exc))
                if on_degrade:
                    on_degrade(name, exc)
        raise failures[-1].error
