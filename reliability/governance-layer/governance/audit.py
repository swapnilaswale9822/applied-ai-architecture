"""Append-only audit trail.

Append-only is the requirement, not a stylistic choice: an audit log that can be edited is
not evidence. Entries are chained by hash so a removed or altered entry breaks verification
rather than disappearing quietly.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

INGEST, RETRIEVE, GENERATE, BLOCK = "ingest", "retrieve", "generate", "block"


@dataclass
class AuditEntry:
    action: str
    tenant_id: str
    actor: str
    at: float
    detail: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    entry_hash: str = ""


class AuditLog:
    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._entries: List[AuditEntry] = []

    def record(self, action: str, tenant_id: str, actor: str, **detail) -> AuditEntry:
        prev = self._entries[-1].entry_hash if self._entries else ""
        entry = AuditEntry(action, tenant_id, actor, self._clock(), detail, prev)
        entry.entry_hash = self._hash(entry)
        self._entries.append(entry)
        return entry

    @staticmethod
    def _hash(entry: AuditEntry) -> str:
        payload = json.dumps(
            {k: v for k, v in asdict(entry).items() if k != "entry_hash"},
            sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def entries(self, tenant_id: Optional[str] = None) -> List[AuditEntry]:
        if tenant_id is None:
            return list(self._entries)
        return [e for e in self._entries if e.tenant_id == tenant_id]

    def verify(self) -> bool:
        """False if any entry was altered or removed after the fact."""
        prev = ""
        for entry in self._entries:
            if entry.prev_hash != prev or entry.entry_hash != self._hash(entry):
                return False
            prev = entry.entry_hash
        return True
