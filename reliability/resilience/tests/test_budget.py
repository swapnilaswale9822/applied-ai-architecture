import pytest

from resilience import Deadline, DeadlineExceeded


class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s


def test_budget_decrements_as_time_passes():
    c = Clock()
    d = Deadline(10.0, clock=c)
    assert d.remaining() == 10.0
    c.advance(3.0)
    assert d.remaining() == 7.0


def test_remaining_never_negative():
    c = Clock()
    d = Deadline(1.0, clock=c)
    c.advance(99.0)
    assert d.remaining() == 0.0
    assert d.expired()


def test_check_raises_once_exhausted():
    c = Clock()
    d = Deadline(1.0, clock=c)
    d.check()  # fine
    c.advance(2.0)
    with pytest.raises(DeadlineExceeded):
        d.check("retrieval")


def test_slice_shrinks_with_the_budget():
    """A slow earlier step must squeeze later ones rather than blowing the total."""
    c = Clock()
    d = Deadline(10.0, clock=c)
    assert d.slice_for(0.5) == 5.0
    c.advance(8.0)          # an earlier hop was slow
    assert d.slice_for(0.5) == 1.0
