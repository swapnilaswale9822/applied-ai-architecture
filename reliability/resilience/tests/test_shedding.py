import pytest

from resilience import BATCH, INTERACTIVE, STANDARD, LoadShed, LoadShedder, SheddingPolicy


def shedder():
    return LoadShedder(SheddingPolicy(
        thresholds={INTERACTIVE: 5000, STANDARD: 1000, BATCH: 200},
        drain_rate_per_second=50.0,
    ))


def test_admits_everything_when_the_queue_is_healthy():
    s = shedder()
    for p in (INTERACTIVE, STANDARD, BATCH):
        s.admit(10, p)


def test_batch_is_sacrificed_first():
    """Shedding the least important work is what keeps interactive latency intact."""
    s = shedder()
    with pytest.raises(LoadShed):
        s.admit(500, BATCH)
    s.admit(500, STANDARD)       # still fine
    s.admit(500, INTERACTIVE)    # still fine


def test_interactive_survives_longest():
    s = shedder()
    for p in (BATCH, STANDARD):
        with pytest.raises(LoadShed):
            s.admit(4000, p)
    s.admit(4000, INTERACTIVE)


def test_everything_sheds_under_extreme_backlog():
    s = shedder()
    with pytest.raises(LoadShed):
        s.admit(9999, INTERACTIVE)


def test_retry_after_reflects_the_actual_backlog():
    """Clients should back off by a real estimate, not a hardcoded guess."""
    s = shedder()
    # 700 over the batch threshold, draining 50/s -> 14s
    assert s.retry_after(900, BATCH) == 14.0
    with pytest.raises(LoadShed) as exc:
        s.admit(900, BATCH)
    assert exc.value.retry_after == 14.0


def test_deeper_backlog_means_longer_backoff():
    s = shedder()
    assert s.retry_after(2000, BATCH) > s.retry_after(900, BATCH)


def test_unknown_priority_is_an_error():
    with pytest.raises(KeyError):
        shedder().admit(10, "urgent-ish")
