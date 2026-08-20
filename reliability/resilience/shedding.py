"""Load shedding by priority.

When the queue is growing faster than it drains, the system has more work than capacity.
Accepting all of it means everything gets slower and eventually times out — the whole
queue fails instead of the least important part of it.

Shedding sacrifices low-priority work early so interactive traffic keeps its latency.
Thresholds are **per priority**: batch work is dropped long before a user-facing request is.

Rejections carry ``Retry-After`` derived from the actual backlog and drain rate, so clients
back off by a real estimate rather than guessing.
"""

from dataclasses import dataclass, field
from typing import Dict

from .errors import LoadShed

INTERACTIVE, STANDARD, BATCH = "interactive", "standard", "batch"


@dataclass
class SheddingPolicy:
    """Queue depth at which each priority starts being rejected."""

    thresholds: Dict[str, int] = field(
        default_factory=lambda: {INTERACTIVE: 5000, STANDARD: 1000, BATCH: 200}
    )
    #: Jobs drained per second, used to estimate Retry-After.
    drain_rate_per_second: float = 50.0

    def threshold_for(self, priority: str) -> int:
        if priority not in self.thresholds:
            raise KeyError(f"unknown priority '{priority}'")
        return self.thresholds[priority]


class LoadShedder:
    def __init__(self, policy: SheddingPolicy = None):
        self.policy = policy or SheddingPolicy()

    def should_shed(self, queue_depth: int, priority: str) -> bool:
        return queue_depth >= self.policy.threshold_for(priority)

    def admit(self, queue_depth: int, priority: str = STANDARD) -> None:
        """Raise ``LoadShed`` (→ HTTP 429) if this priority is over its threshold."""
        if self.should_shed(queue_depth, priority):
            raise LoadShed(self.retry_after(queue_depth, priority))

    def retry_after(self, queue_depth: int, priority: str) -> float:
        """Seconds until the backlog is expected to fall under this priority's threshold."""
        excess = max(0, queue_depth - self.policy.threshold_for(priority))
        rate = max(1e-9, self.policy.drain_rate_per_second)
        return round(excess / rate, 1)
