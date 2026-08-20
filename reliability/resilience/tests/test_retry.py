import random

import pytest

from resilience import Deadline, DeadlineExceeded, PermanentError, RetryableError, RetryPolicy
from resilience.retry import retry_call


def test_succeeds_without_retrying():
    calls = []
    assert retry_call(lambda: calls.append(1) or "ok", sleep=lambda _: None) == "ok"
    assert len(calls) == 1


def test_retries_transient_then_succeeds():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RetryableError("503")
        return "ok"

    assert retry_call(flaky, RetryPolicy(max_attempts=3), sleep=lambda _: None) == "ok"
    assert len(attempts) == 3


def test_permanent_error_is_never_retried():
    """A 400 will be a 400 next time. Retrying costs money to fail identically."""
    attempts = []

    def bad_request():
        attempts.append(1)
        raise PermanentError("400")

    with pytest.raises(PermanentError):
        retry_call(bad_request, RetryPolicy(max_attempts=5), sleep=lambda _: None)
    assert len(attempts) == 1


def test_raises_last_error_after_exhausting_attempts():
    with pytest.raises(RetryableError):
        retry_call(lambda: (_ for _ in ()).throw(RetryableError("down")),
                   RetryPolicy(max_attempts=3), sleep=lambda _: None)


def test_backoff_is_exponential_when_jitter_disabled():
    p = RetryPolicy(base_delay=0.5, max_delay=100.0, jitter=False)
    assert [p.delay_for(i) for i in (1, 2, 3, 4)] == [0.5, 1.0, 2.0, 4.0]


def test_backoff_respects_the_cap():
    p = RetryPolicy(base_delay=1.0, max_delay=3.0, jitter=False)
    assert p.delay_for(10) == 3.0


def test_full_jitter_spreads_retries_across_the_whole_interval():
    """Fixed backoff makes every client retry in the same instant and re-break the
    provider it is waiting for. Full jitter must produce a spread, not a constant."""
    p = RetryPolicy(base_delay=1.0, max_delay=64.0, jitter=True)
    rng = random.Random(42)
    samples = [p.delay_for(4, rng) for _ in range(200)]
    cap = 8.0  # 1.0 * 2**3
    assert all(0.0 <= s <= cap for s in samples)
    assert len(set(round(s, 6) for s in samples)) > 100   # genuinely spread
    assert min(samples) < cap * 0.2 and max(samples) > cap * 0.8


def test_never_sleeps_past_the_deadline():
    """Backing off longer than the budget just wastes the remaining time to fail anyway."""
    class Clock:
        t = 0.0
        def __call__(self): return self.t

    c = Clock()
    d = Deadline(1.0, clock=c)
    policy = RetryPolicy(max_attempts=5, base_delay=10.0, jitter=False)

    with pytest.raises(DeadlineExceeded):
        retry_call(lambda: (_ for _ in ()).throw(RetryableError("503")),
                   policy, deadline=d, sleep=lambda _: None)
