"""Deadline propagation.

The common mistake is per-call timeouts: retrieval 5s, model 30s, tool 10s, two retries
each. Every individual number looks reasonable and the worst case is over two minutes.

A deadline is allocated **once per request** and decremented as it is spent. Every hop asks
how much time is left rather than how long it is individually allowed to take.
"""

import time
from typing import Callable, Optional

from .errors import DeadlineExceeded


class Deadline:
    """A shrinking time budget shared by every step in one request."""

    def __init__(self, budget_seconds: float, clock: Optional[Callable[[], float]] = None):
        self._clock = clock or time.monotonic
        self._budget = float(budget_seconds)
        self._start = self._clock()

    def remaining(self) -> float:
        """Seconds left. Never negative."""
        return max(0.0, self._budget - (self._clock() - self._start))

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def check(self, step: str = "step") -> None:
        """Raise if the budget is gone. Call before starting expensive work."""
        if self.expired():
            raise DeadlineExceeded(f"budget exhausted before {step}")

    def slice_for(self, fraction: float) -> float:
        """Portion of the *remaining* budget to hand to one hop.

        Fractional rather than absolute so a slow earlier step automatically squeezes the
        later ones instead of blowing the total.
        """
        if not 0.0 < fraction <= 1.0:
            raise ValueError("fraction must be in (0, 1]")
        return self.remaining() * fraction
