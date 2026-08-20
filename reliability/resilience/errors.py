"""Error taxonomy.

The single most important distinction in this package: **is this error worth retrying?**
Retrying a 400 wastes money and latency to get the same 400 back. Retrying a 503 is the
whole point. Everything else here follows from that split.
"""


class ResilienceError(Exception):
    """Base for errors raised by this package."""


class RetryableError(ResilienceError):
    """Transient — the same call may succeed later. 429, 503, timeouts, connection resets."""


class PermanentError(ResilienceError):
    """Terminal — retrying cannot help. 400, 401, 404, schema violations."""


class DeadlineExceeded(ResilienceError):
    """The request's total time budget is spent. Never retryable: the budget is gone."""


class CircuitOpen(ResilienceError):
    """The breaker for this dependency is open; the call was rejected without being made."""

    def __init__(self, name: str, retry_after: float):
        super().__init__(f"circuit '{name}' is open; retry in {retry_after:.1f}s")
        self.name = name
        self.retry_after = retry_after


class LoadShed(ResilienceError):
    """Rejected to protect the system. Maps to HTTP 429 with Retry-After."""

    def __init__(self, retry_after: float):
        super().__init__(f"load shed; retry in {retry_after:.1f}s")
        self.retry_after = retry_after


class BulkheadFull(ResilienceError):
    """This workload class is at its concurrency limit. Other classes are unaffected."""
