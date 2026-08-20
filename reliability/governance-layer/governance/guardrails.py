"""Runtime guardrails: checks before the model sees input, and before the user sees output.

Pre-hooks fail closed — a suspected injection is refused rather than passed through with a
warning. Post-hooks fail closed too: an answer that cannot be traced to a retrieved source
is withheld, because an ungrounded answer in a regulated domain is indistinguishable from
a correct one right up until it matters.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .pii import contains_pii, scrub

INJECTION_MARKERS = (
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts)",
    r"disregard\s+(your|the)\s+(instructions|rules|system\s+prompt)",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions)",
    r"you\s+are\s+now\s+(a|an|in)\b",
    r"pretend\s+(you\s+are|to\s+be)\b",
    r"developer\s+mode",
)
_INJECTION = [re.compile(p, re.I) for p in INJECTION_MARKERS]


class GuardrailTripped(Exception):
    def __init__(self, guardrail: str, reason: str):
        super().__init__(f"{guardrail}: {reason}")
        self.guardrail = guardrail
        self.reason = reason


@dataclass
class GuardrailResult:
    allowed: bool
    text: str
    trips: List[str] = field(default_factory=list)


def check_input(text: str, redact_pii: bool = True) -> GuardrailResult:
    """Pre-hook: injection detection, then PII redaction.

    PII is redacted rather than rejected. Real support tickets contain personal data as a
    matter of course; refusing them would make the agent useless, so the data is removed
    before it reaches the model or any log.
    """
    trips: List[str] = []
    for pattern in _INJECTION:
        if pattern.search(text):
            return GuardrailResult(False, text, ["prompt_injection"])

    out = text
    if redact_pii and contains_pii(text):
        out, kinds = scrub(text)
        trips.extend(f"pii:{k}" for k in kinds)
    return GuardrailResult(True, out, trips)


def check_output(
    text: str,
    citations: Optional[List[str]] = None,
    retrieved_sources: Optional[List[str]] = None,
    require_grounding: bool = True,
) -> GuardrailResult:
    """Post-hook: no leaked PII, and every claim traceable to something retrieved."""
    trips: List[str] = []
    if contains_pii(text):
        trips.append("pii_in_output")
        return GuardrailResult(False, text, trips)

    if require_grounding:
        citations = citations or []
        sources = retrieved_sources or []
        if not citations:
            return GuardrailResult(False, text, ["ungrounded"])
        fabricated = [c for c in citations if c not in sources]
        if fabricated:
            # Worse than no citation: it looks verified.
            return GuardrailResult(False, text, ["fabricated_citation"])
    return GuardrailResult(True, text, trips)
