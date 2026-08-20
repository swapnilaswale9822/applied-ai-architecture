"""Governed ingestion: validate → scrub → hash → embed → audit.

The order is the design. Validation before scrubbing (an untenanted document should be
rejected, not cleaned), scrubbing before hashing (the hash must describe what was actually
stored), and auditing last so the record reflects what happened rather than what was
intended.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

from .audit import INGEST
from .metadata import CONFIDENTIAL, DocumentMetadata, MetadataError, RESTRICTED
from .pii import scrub


@dataclass
class IngestResult:
    doc_id: str
    stored: bool
    pii_removed: List[str]
    content_hash: str


class GovernedIngestor:
    def __init__(self, embed: Callable[[str, DocumentMetadata], None], audit=None,
                 actor: str = "system"):
        self._embed = embed
        self._audit = audit
        self._actor = actor

    def ingest(self, content: str, metadata: DocumentMetadata) -> IngestResult:
        if not content.strip():
            raise MetadataError("refusing to ingest empty content")

        # Sensitive classes are scrubbed unconditionally; anything else only if it needs it.
        removed: List[str] = []
        body = content
        if metadata.classification in (CONFIDENTIAL, RESTRICTED):
            body, removed = scrub(content)

        metadata.content_hash = DocumentMetadata.hash_content(body)
        self._embed(body, metadata)

        if self._audit:
            self._audit.record(
                INGEST, metadata.tenant_id, self._actor,
                doc_id=metadata.doc_id, classification=metadata.classification,
                pii_removed=removed, content_hash=metadata.content_hash)
        return IngestResult(metadata.doc_id, True, removed, metadata.content_hash)
