import pytest

from resilience import FallbackChain, PermanentError, RetryableError


def boom(msg="down"):
    def _f():
        raise RetryableError(msg)
    return _f


def test_primary_success_reports_no_degradation():
    out = FallbackChain().tier("primary", lambda: "A").tier("cache", lambda: "C").run()
    assert (out.value, out.tier, out.degraded) == ("A", "primary", False)


def test_falls_through_to_the_next_tier():
    out = FallbackChain().tier("primary", boom()).tier("secondary", lambda: "B").run()
    assert out.value == "B" and out.tier == "secondary"
    assert out.degraded and [a.tier for a in out.degraded_from] == ["primary"]


def test_degrades_all_the_way_to_an_explicit_refusal():
    """Running out of options should produce an honest answer, not a 500 and not a guess."""
    out = (FallbackChain()
           .tier("primary", boom())
           .tier("secondary", boom())
           .tier("cache", boom("miss"))
           .tier("refusal", lambda: "I can't answer that reliably right now.")
           .run())
    assert out.tier == "refusal"
    assert [a.tier for a in out.degraded_from] == ["primary", "secondary", "cache"]


def test_permanent_error_short_circuits_the_whole_chain():
    """A malformed request will be malformed for the cheaper model too."""
    tried = []

    def bad():
        tried.append("primary")
        raise PermanentError("400")

    chain = FallbackChain().tier("primary", bad).tier("secondary", lambda: tried.append("secondary"))
    with pytest.raises(PermanentError):
        chain.run()
    assert tried == ["primary"]


def test_degradation_is_observable():
    """Silent degradation is how quality drops for a week before anyone notices."""
    seen = []
    FallbackChain().tier("primary", boom()).tier("secondary", lambda: "B").run(
        on_degrade=lambda tier, exc: seen.append(tier))
    assert seen == ["primary"]


def test_empty_chain_is_a_programming_error():
    with pytest.raises(ValueError):
        FallbackChain().run()
