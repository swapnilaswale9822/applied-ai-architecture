import pytest

from resilience import (CLOSED, HALF_OPEN, OPEN, CircuitBreaker, CircuitBreakerRegistry,
                        CircuitOpen, PermanentError, RetryableError)


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s


def breaker(clock, **kw):
    kw.setdefault("min_calls", 4)
    kw.setdefault("error_rate_threshold", 0.5)
    kw.setdefault("recovery_timeout", 10.0)
    kw.setdefault("window_seconds", 30.0)
    return CircuitBreaker("provider", clock=clock, **kw)


def fail(cb, n=1):
    for _ in range(n):
        with pytest.raises(RetryableError):
            cb.call(lambda: (_ for _ in ()).throw(RetryableError("down")))


def succeed(cb, n=1):
    for _ in range(n):
        cb.call(lambda: "ok")


def test_starts_closed_and_passes_calls_through():
    cb = breaker(Clock())
    assert cb.state == CLOSED
    assert cb.call(lambda: "ok") == "ok"


def test_trips_on_rolling_error_rate():
    cb = breaker(Clock())
    fail(cb, 4)
    assert cb.state == OPEN


def test_does_not_trip_below_min_calls():
    """One early failure on thin traffic is noise, not an outage signal."""
    cb = breaker(Clock(), min_calls=10)
    fail(cb, 3)
    assert cb.state == CLOSED


def test_trips_on_partial_failure_rate_not_consecutive_failures():
    """The real-world degradation: ~50% failing, never five in a row.
    A consecutive-count breaker would never trip here."""
    cb = breaker(Clock(), min_calls=8, error_rate_threshold=0.5)
    for _ in range(4):
        succeed(cb)
        fail(cb)
    assert cb.state == OPEN


def test_open_circuit_rejects_without_calling_the_dependency():
    cb = breaker(Clock())
    fail(cb, 4)
    called = []
    with pytest.raises(CircuitOpen) as exc:
        cb.call(lambda: called.append(1))
    assert called == []                      # the dependency was never touched
    assert exc.value.retry_after > 0         # and the caller is told when to come back


def test_moves_to_half_open_after_recovery_timeout():
    c = Clock()
    cb = breaker(c, recovery_timeout=10.0)
    fail(cb, 4)
    c.advance(9.0)
    assert cb.state == OPEN
    c.advance(2.0)
    assert cb.state == HALF_OPEN


def test_half_open_admits_exactly_one_probe():
    """The bug this prevents: every waiting caller floods a still-recovering service
    the instant the timer expires."""
    c = Clock()
    cb = breaker(c, recovery_timeout=10.0)
    fail(cb, 4)
    c.advance(11.0)

    started = []

    def slow_probe():
        started.append(1)
        raise RetryableError("still down")   # the probe has not reported back yet

    # First caller becomes the probe.
    with pytest.raises(RetryableError):
        cb.call(slow_probe)
    assert len(started) == 1

    # It failed, so the circuit is open again and the next caller is rejected outright.
    with pytest.raises(CircuitOpen):
        cb.call(lambda: started.append(1))
    assert len(started) == 1


def test_successful_probe_closes_the_circuit():
    c = Clock()
    cb = breaker(c, recovery_timeout=10.0)
    fail(cb, 4)
    c.advance(11.0)
    assert cb.call(lambda: "recovered") == "recovered"
    assert cb.state == CLOSED


def test_failed_probe_reopens_and_restarts_the_timer():
    c = Clock()
    cb = breaker(c, recovery_timeout=10.0)
    fail(cb, 4)
    c.advance(11.0)
    assert cb.state == HALF_OPEN
    fail(cb, 1)
    assert cb.state == OPEN
    c.advance(5.0)
    assert cb.state == OPEN          # timer restarted, not resumed
    c.advance(6.0)
    assert cb.state == HALF_OPEN


def test_client_errors_do_not_open_the_circuit():
    """Otherwise one caller sending malformed requests takes the dependency
    offline for everybody."""
    cb = breaker(Clock(), min_calls=2)
    for _ in range(10):
        with pytest.raises(PermanentError):
            cb.call(lambda: (_ for _ in ()).throw(PermanentError("400")))
    assert cb.state == CLOSED


def test_old_failures_leave_the_window():
    c = Clock()
    cb = breaker(c, min_calls=4, window_seconds=30.0)
    fail(cb, 3)
    c.advance(31.0)          # those failures are now ancient history
    fail(cb, 3)
    assert cb.state == CLOSED   # only 3 in-window failures, below min_calls


def test_breakers_are_isolated_per_dependency():
    """A shared breaker means one vendor's outage stops calls to a healthy one."""
    c = Clock()
    reg = CircuitBreakerRegistry(min_calls=4, error_rate_threshold=0.5,
                                 recovery_timeout=10.0, clock=c)
    fail(reg.get("anthropic"), 4)
    assert reg.get("anthropic").state == OPEN
    assert reg.get("openai").state == CLOSED
    assert reg.get("openai").call(lambda: "ok") == "ok"
