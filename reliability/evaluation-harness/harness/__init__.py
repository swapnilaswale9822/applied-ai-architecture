"""Agent-agnostic evaluation harness: golden sets, tiered gates, CI verdict.

    from harness import GoldenSet, Golden, evaluate, NORMAL, ADVERSARIAL

Mirrors the structure of the Promptfoo-backed evaluation service described in
``reliability/README.md``, reduced to a dependency-free core so the behaviour is testable
without a model provider or a database.
"""

from .dataset import (ADVERSARIAL, AMBIGUOUS, CLASSES, EDGE, NORMAL, Golden, GoldenSet,
                      from_production_trace)
from .gates import (DEFAULT_TIERS, FAIL, MISCONFIGURED, PASS, QUALITY, SAFETY, STYLE,
                    Tier, TierResult, Verdict)
from .runner import CaseResult, RunResult, coverage_report, evaluate
from .scorers import SCORERS

__all__ = [
    "Golden", "GoldenSet", "from_production_trace",
    "NORMAL", "EDGE", "AMBIGUOUS", "ADVERSARIAL", "CLASSES",
    "evaluate", "RunResult", "CaseResult", "coverage_report",
    "Verdict", "TierResult", "Tier", "DEFAULT_TIERS",
    "SAFETY", "QUALITY", "STYLE", "PASS", "FAIL", "MISCONFIGURED", "SCORERS",
]
