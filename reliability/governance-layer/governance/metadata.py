"""Document metadata contract, validated **before** anything is embedded.

Validating at ingest rather than at retrieval is the whole point. A document embedded
without a tenant or a classification is already a leak waiting to happen — and by the time
it surfaces in someone else's answer, the fix is a re-index, not a patch.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED = "public", "internal", "confidential", "restricted"
CLASSIFICATIONS = (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)


class MetadataError(ValueError):
    """The document does not satisfy the contract and must not be ingested."""


@dataclass
class DocumentMetadata:
    doc_id: str
    tenant_id: str
    classification: str
    source: str
    effective_from: float
    effective_until: Optional[float] = None
    content_hash: str = ""
    version: int = 1
    tags: list = field(default_factory=list)

    def __post_init__(self):
        if not self.doc_id:
            raise MetadataError("doc_id is required")
        if not self.tenant_id:
            raise MetadataError("tenant_id is required — untenanted documents cannot be stored")
        if self.classification not in CLASSIFICATIONS:
            raise MetadataError(
                f"classification must be one of {CLASSIFICATIONS}, got {self.classification!r}")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise MetadataError("effective_until must be after effective_from")

    def is_fresh(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        if now < self.effective_from:
            return False
        return self.effective_until is None or now < self.effective_until

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]
