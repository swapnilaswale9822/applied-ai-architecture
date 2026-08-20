"""The composed call path, and the LLM-specific wrinkle.

Order matters. Cheapest rejection first:

    shed (is the system overloaded?)
      └─ bulkhead (is this workload class at its limit?)
           └─ breaker (is this provider known-broken?)
                └─ retry (transient? try again with jitter)
                     └─ fallback (still failing? degrade)

Retry sits *inside* the breaker, not outside: retries against a dependency that is already
known to be down are exactly what the breaker exists to prevent.
"""

from .budget import Deadline
from .circuit_breaker import CircuitBreakerRegistry
from .errors import PermanentError, RetryableError
from .fallback import FallbackChain
from .retry import RetryPolicy, retry_call
from .shedding import LoadShedder

breakers = CircuitBreakerRegistry(error_rate_threshold=0.5, min_calls=10, recovery_timeout=15.0)
shedder = LoadShedder()


def guarded_call(provider: str, fn, deadline: Deadline, policy: RetryPolicy = None):
    """One dependency call, wrapped in breaker + retry, respecting the shared deadline."""
    breaker = breakers.get(provider)
    return retry_call(
        lambda: breaker.call(fn),
        policy=policy or RetryPolicy(max_attempts=3),
        deadline=deadline,
    )


def answer(question: str, queue_depth: int, clients: dict, cache: dict):
    """Full path: shed → breaker+retry on primary → degrade → honest refusal."""
    shedder.admit(queue_depth, priority="interactive")
    deadline = Deadline(20.0)

    chain = (
        FallbackChain()
        .tier("primary", lambda: guarded_call(
            "anthropic", lambda: clients["primary"](question), deadline))
        .tier("secondary", lambda: guarded_call(
            "openai", lambda: clients["secondary"](question), deadline))
        .tier("cache", lambda: cache[question])
        .tier("refusal", lambda:
              "I can't answer that reliably right now — please try again shortly.")
    )
    return chain.run()


# --- the part that is specific to language models ------------------------------------

def call_with_validation(fn, validate, policy: RetryPolicy = None, deadline: Deadline = None):
    """Retry on *invalid output*, not just on transport errors.

    Retrying an HTTP call is idempotent; retrying an LLM call is not. At temperature > 0 the
    second attempt returns a *different* answer — which is useless if you are retrying a
    transport blip, but is exactly what you want when the model returned unparseable JSON or
    an ungrounded claim.

    So the retryable condition for a model call is "the response failed validation", and the
    validator is the retry predicate. Without this pairing, retries either do nothing useful
    or quietly produce an inconsistent answer.
    """
    def attempt():
        result = fn()
        if not validate(result):
            raise RetryableError("response failed validation")
        return result

    return retry_call(attempt, policy=policy or RetryPolicy(max_attempts=3), deadline=deadline)


def classify_http(status: int) -> BaseException:
    """Map a provider status code to the retry taxonomy.

    429 and 5xx are transient. 4xx means the request was wrong and will be wrong again —
    retrying it burns budget to receive the same rejection.
    """
    if status == 429 or status >= 500:
        return RetryableError(f"provider returned {status}")
    return PermanentError(f"provider returned {status}")
