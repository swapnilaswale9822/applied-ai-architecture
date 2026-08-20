"""Resilience patterns for LLM-backed services.

Each module is independent and stdlib-only. Clocks, sleeps and randomness are injectable so
the behaviour can be tested deterministically rather than by waiting — see ``tests/``.

    from resilience import Deadline, RetryPolicy, retry_call, CircuitBreakerRegistry

See ``examples.py`` for the composed call path: shed → bulkhead → breaker → retry → fallback.
"""

from .budget import Deadline
from .bulkhead import Bulkhead, BulkheadRegistry
from .circuit_breaker import CLOSED, HALF_OPEN, OPEN, CircuitBreaker, CircuitBreakerRegistry
from .errors import (
    BulkheadFull,
    CircuitOpen,
    DeadlineExceeded,
    LoadShed,
    PermanentError,
    ResilienceError,
    RetryableError,
)
from .fallback import FallbackChain, Outcome
from .retry import RetryPolicy, retry_call
from .shedding import BATCH, INTERACTIVE, STANDARD, LoadShedder, SheddingPolicy

__all__ = [
    "Deadline", "RetryPolicy", "retry_call",
    "CircuitBreaker", "CircuitBreakerRegistry", "CLOSED", "OPEN", "HALF_OPEN",
    "Bulkhead", "BulkheadRegistry", "FallbackChain", "Outcome",
    "LoadShedder", "SheddingPolicy", "INTERACTIVE", "STANDARD", "BATCH",
    "ResilienceError", "RetryableError", "PermanentError",
    "DeadlineExceeded", "CircuitOpen", "LoadShed", "BulkheadFull",
]
