"""Bulkhead isolation.

Named for ship compartments: a hull breach floods one section, not the vessel. Here the
breach is a slow dependency, and the compartment is a concurrency limit per workload class.

Without it, one tenant's bulk ingest occupies every worker and interactive traffic queues
behind it — the classic noisy-neighbour outage where nothing has actually failed, it is
just all busy. In production this is expressed as separate Celery queues and worker pools;
in-process, it is a semaphore per class.

Rejecting fast is the point. A caller that gets ``BulkheadFull`` immediately can shed or
degrade; a caller blocked behind a full queue just consumes a connection while it waits.
"""

import threading
from contextlib import contextmanager
from typing import Dict

from .errors import BulkheadFull


class Bulkhead:
    def __init__(self, name: str, max_concurrent: int):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self.name = name
        self.max_concurrent = max_concurrent
        self._sem = threading.BoundedSemaphore(max_concurrent)
        self._active = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        with self._lock:
            return self._active

    @contextmanager
    def slot(self, timeout: float = 0.0):
        """Acquire a slot or raise ``BulkheadFull``. Default is non-blocking by design."""
        if not self._sem.acquire(blocking=timeout > 0, timeout=timeout or None):
            raise BulkheadFull(f"bulkhead '{self.name}' full ({self.max_concurrent} in flight)")
        with self._lock:
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1
            self._sem.release()


class BulkheadRegistry:
    """One bulkhead per workload class — interactive, ingest, batch, learning."""

    def __init__(self, limits: Dict[str, int]):
        self._bulkheads = {n: Bulkhead(n, c) for n, c in limits.items()}

    def get(self, name: str) -> Bulkhead:
        if name not in self._bulkheads:
            raise KeyError(f"no bulkhead configured for workload class '{name}'")
        return self._bulkheads[name]

    def snapshot(self) -> Dict[str, str]:
        return {n: f"{b.active}/{b.max_concurrent}" for n, b in self._bulkheads.items()}
