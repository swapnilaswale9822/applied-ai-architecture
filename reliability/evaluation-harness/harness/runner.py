"""Run a golden set against an agent and produce a gate verdict.

The agent is treated as a **black box over a callable**: give it an input, get back a
response dict. One harness therefore covers every agent, and evaluation never depends on
an agent's internals — which is what stops the suite rotting each time an implementation
changes.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .dataset import CLASSES, GoldenSet
from .gates import DEFAULT_TIERS, STYLE, TierResult, Verdict
from .scorers import SCORERS

Agent = Callable[[str], Dict[str, Any]]


@dataclass
class CaseResult:
    golden_id: str
    scenario_class: str
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(a["passed"] for a in self.assertions)

    def failures(self) -> List[Dict[str, Any]]:
        return [a for a in self.assertions if not a["passed"]]


@dataclass
class RunResult:
    cases: List[CaseResult]
    verdict: Verdict

    def failed_cases(self) -> List[CaseResult]:
        return [c for c in self.cases if not c.passed]

    def summary(self) -> str:
        head = f"{sum(1 for c in self.cases if c.passed)}/{len(self.cases)} cases passed"
        return f"{head}\n{self.verdict.report()}"


def evaluate(agent: Agent, golden_set: GoldenSet, tiers=None,
             require_classes: bool = True) -> RunResult:
    tiers = tiers or DEFAULT_TIERS
    tallies = {name: [0, 0] for name in tiers}   # tier -> [passed, total]
    cases: List[CaseResult] = []

    for golden in golden_set.goldens:
        case = CaseResult(golden.id, golden.scenario_class)
        try:
            response = agent(golden.input)
        except BaseException as exc:
            # A crash is a failure of every tier the case would have exercised, never a skip.
            case.error = f"{type(exc).__name__}: {exc}"
            for name in _tiers_for(golden.expect):
                tallies[name][1] += 1
            cases.append(case)
            continue

        for assertion, expected in golden.expect.items():
            if assertion not in SCORERS:
                raise ValueError(f"unknown assertion '{assertion}' on golden '{golden.id}'")
            scorer, tier = SCORERS[assertion]
            passed, detail = scorer(response, expected)
            case.assertions.append({"assertion": assertion, "tier": tier,
                                    "passed": passed, "detail": detail})
            tallies[tier][1] += 1
            if passed:
                tallies[tier][0] += 1
        cases.append(case)

    results = {name: TierResult(name, tallies[name][0], tallies[name][1],
                                t.threshold, t.blocking)
               for name, t in tiers.items()}
    missing = golden_set.missing_classes() if require_classes else []
    return RunResult(cases, Verdict(results, missing))


def _tiers_for(expect: Dict[str, Any]) -> List[str]:
    return [SCORERS[a][1] for a in expect if a in SCORERS] or [STYLE]


def coverage_report(golden_set: GoldenSet) -> str:
    counts = golden_set.coverage()
    return " · ".join(f"{c}: {counts[c]}" for c in CLASSES)
