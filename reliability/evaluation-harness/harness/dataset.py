"""Golden datasets, split by scenario class.

Testing only the happy path is how a prompt change ships a regression. The four classes
exist because they fail in different ways and carry different consequences:

- ``normal``       expected usage. Catches outright breakage.
- ``edge``         boundaries — empty input, very long input, unicode, malformed.
- ``ambiguous``    underspecified. The correct behaviour is usually to *ask*, not to guess.
                   Systems that always answer score well here and are wrong in production.
- ``adversarial``  injection, jailbreak, PII extraction. Failures here are incidents, not
                   quality dips — which is why they gate at 100% (see ``gates.py``).
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

NORMAL, EDGE, AMBIGUOUS, ADVERSARIAL = "normal", "edge", "ambiguous", "adversarial"
CLASSES = (NORMAL, EDGE, AMBIGUOUS, ADVERSARIAL)


@dataclass
class Golden:
    id: str
    scenario_class: str
    input: str
    #: Assertions to apply, e.g. {"contains": "vpn", "grounded": True, "must_refuse": True}
    expect: Dict[str, Any] = field(default_factory=dict)
    #: Free-form provenance — "handwritten", "generated", or a production trace id.
    source: str = "handwritten"

    def __post_init__(self):
        if self.scenario_class not in CLASSES:
            raise ValueError(f"unknown scenario class '{self.scenario_class}'")


class GoldenSet:
    def __init__(self, name: str, goldens: Optional[List[Golden]] = None):
        self.name = name
        self.goldens: List[Golden] = list(goldens or [])

    def add(self, golden: Golden) -> "GoldenSet":
        if any(g.id == golden.id for g in self.goldens):
            raise ValueError(f"duplicate golden id '{golden.id}'")
        self.goldens.append(golden)
        return self

    def by_class(self, scenario_class: str) -> List[Golden]:
        return [g for g in self.goldens if g.scenario_class == scenario_class]

    def coverage(self) -> Dict[str, int]:
        return {c: len(self.by_class(c)) for c in CLASSES}

    def missing_classes(self) -> List[str]:
        """A suite with no adversarial cases is not a suite — it is a demo."""
        return [c for c, n in self.coverage().items() if n == 0]

    def to_json(self) -> str:
        return json.dumps({"name": self.name,
                           "goldens": [asdict(g) for g in self.goldens]}, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "GoldenSet":
        data = json.loads(raw)
        return cls(data["name"], [Golden(**g) for g in data["goldens"]])


def from_production_trace(trace: Dict[str, Any], scenario_class: str = NORMAL) -> Golden:
    """Turn a failed production trace into a permanent regression test.

    This is the loop that compounds: every real-world failure becomes a case that can never
    silently recur. It is also the only test-growth strategy that keeps pace with a
    non-deterministic system, because you cannot enumerate the failure modes up front.
    """
    expect: Dict[str, Any] = {}
    if trace.get("failure") == "ungrounded":
        expect["grounded"] = True
    elif trace.get("failure") == "leaked_pii":
        expect["no_pii"] = True
    elif trace.get("failure") == "followed_injection":
        expect["must_refuse"] = True
        scenario_class = ADVERSARIAL
    if trace.get("expected_substring"):
        expect["contains"] = trace["expected_substring"]

    return Golden(
        id=f"regression-{trace['trace_id']}",
        scenario_class=scenario_class,
        input=trace["input"],
        expect=expect,
        source=f"trace:{trace['trace_id']}",
    )
