"""PII redaction at the ingest boundary.

Scrubbing on the way in rather than on the way out: once a value is embedded it exists in
the vector store, in backups, and in any index built from it. Redacting it from responses
leaves every copy in place.
"""

import re
from typing import Dict, List, Tuple

PATTERNS: Dict[str, re.Pattern] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[ -]?)?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


def scrub(text: str) -> Tuple[str, List[str]]:
    """Return redacted text and the kinds of PII found.

    Order matters: SSN and card are matched before the looser phone pattern, which would
    otherwise claim their digits and mislabel the redaction in the audit trail.
    """
    found: List[str] = []
    out = text
    for kind in ("ssn", "card", "email", "phone"):
        pattern = PATTERNS[kind]
        if pattern.search(out):
            found.append(kind)
            out = pattern.sub(f"[REDACTED:{kind}]", out)
    return out, found


def contains_pii(text: str) -> bool:
    return any(p.search(text) for p in PATTERNS.values())
