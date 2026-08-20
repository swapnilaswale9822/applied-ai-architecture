"""A governance layer for a retrieval-backed agent.

Governance is a cross-cutting concern, so it is enforced at four boundaries rather than
bolted on at the end:

    ingest  ──►  store  ──►  retrieve  ──►  runtime
    metadata     tenant +     tenant scope    pre/post
    validation   freshness    + freshness     guardrails
    + PII scrub  flags        (always)        + audit
"""

from .access import AccessDenied, Document, GovernedRetriever
from .audit import AuditEntry, AuditLog, BLOCK, GENERATE, INGEST, RETRIEVE
from .guardrails import GuardrailResult, GuardrailTripped, check_input, check_output
from .ingestion import GovernedIngestor, IngestResult
from .metadata import (CLASSIFICATIONS, CONFIDENTIAL, INTERNAL, PUBLIC, RESTRICTED,
                       DocumentMetadata, MetadataError)
from .pii import contains_pii, scrub

__all__ = [
    "DocumentMetadata", "MetadataError", "CLASSIFICATIONS",
    "PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED",
    "GovernedRetriever", "Document", "AccessDenied",
    "GovernedIngestor", "IngestResult",
    "check_input", "check_output", "GuardrailResult", "GuardrailTripped",
    "AuditLog", "AuditEntry", "INGEST", "RETRIEVE", "GENERATE", "BLOCK",
    "scrub", "contains_pii",
]
