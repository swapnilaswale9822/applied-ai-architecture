import threading

import pytest

from resilience import Bulkhead, BulkheadFull, BulkheadRegistry


def test_allows_up_to_the_limit():
    b = Bulkhead("ingest", 2)
    with b.slot():
        with b.slot():
            assert b.active == 2
    assert b.active == 0


def test_rejects_immediately_when_full():
    """Fast rejection lets the caller shed or degrade; blocking just holds a connection."""
    b = Bulkhead("ingest", 1)
    with b.slot():
        with pytest.raises(BulkheadFull):
            with b.slot():
                pass


def test_slot_is_released_even_when_the_body_raises():
    b = Bulkhead("ingest", 1)
    with pytest.raises(RuntimeError):
        with b.slot():
            raise RuntimeError("handler blew up")
    assert b.active == 0
    with b.slot():
        pass


def test_one_saturated_class_does_not_starve_another():
    """The noisy-neighbour outage: bulk ingest occupies every worker and interactive
    traffic queues behind it, even though nothing has actually failed."""
    reg = BulkheadRegistry({"interactive": 2, "ingest": 1})
    with reg.get("ingest").slot():
        with pytest.raises(BulkheadFull):
            with reg.get("ingest").slot():
                pass
        with reg.get("interactive").slot():      # unaffected
            assert reg.get("interactive").active == 1


def test_limit_holds_under_concurrency():
    b = Bulkhead("ingest", 3)
    peak, lock, done = [0], threading.Lock(), threading.Event()

    def worker():
        try:
            with b.slot(timeout=1.0):
                with lock:
                    peak[0] = max(peak[0], b.active)
                done.wait(0.02)
        except BulkheadFull:
            pass

    threads = [threading.Thread(target=worker) for _ in range(12)]
    [t.start() for t in threads]
    done.set()
    [t.join() for t in threads]
    assert peak[0] <= 3
    assert b.active == 0


def test_unknown_workload_class_is_an_error():
    with pytest.raises(KeyError):
        BulkheadRegistry({"interactive": 1}).get("nope")
