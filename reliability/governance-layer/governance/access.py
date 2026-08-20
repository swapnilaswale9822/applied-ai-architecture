"""Tenant-scoped retrieval.

The core claim of this module: **isolation you can forget to apply is not isolation.**

The common design puts a tenant filter in the query the application builds. That works
until one code path forgets it, and the bug is silent — the caller gets *more* results, not
an error, so nothing looks wrong until a customer sees another customer's document.

Here the filter cannot be omitted. ``GovernedRetriever`` is constructed with a tenant and
applies the predicate itself; the caller has no parameter with which to widen the scope.
Freshness and classification ceilings are enforced at the same boundary, for the same reason.
"""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from .metadata import CLASSIFICATIONS, DocumentMetadata

#: Ordered least to most sensitive; a principal may read at or below its ceiling.
_RANK = {name: i for i, name in enumerate(CLASSIFICATIONS)}


@dataclass
class Document:
    metadata: DocumentMetadata
    content: str


class AccessDenied(PermissionError):
    """Raised when a caller asks for something outside its own scope."""


class GovernedRetriever:
    """Wraps a raw search function and constrains every result it returns."""

    def __init__(
        self,
        search: Callable[[str, int], List[Document]],
        tenant_id: str,
        max_classification: str = "internal",
        clock: Optional[Callable[[], float]] = None,
        audit=None,
        actor: str = "system",
    ):
        if not tenant_id:
            raise ValueError("GovernedRetriever requires a tenant_id")
        if max_classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown classification '{max_classification}'")
        self._search = search
        self.tenant_id = tenant_id
        self.max_classification = max_classification
        self._clock = clock
        self._audit = audit
        self._actor = actor

    def _now(self) -> Optional[float]:
        return self._clock() if self._clock else None

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        # Over-fetch, then filter: the raw store may return other tenants' rows, and this
        # boundary is the thing that guarantees they never reach the caller.
        raw = self._search(query, k * 4)
        now = self._now()

        allowed = [
            d for d in raw
            if d.metadata.tenant_id == self.tenant_id
            and d.metadata.is_fresh(now)
            and _RANK[d.metadata.classification] <= _RANK[self.max_classification]
        ]
        kept = allowed[:k]

        if self._audit:
            self._audit.record(
                "retrieve", self.tenant_id, self._actor,
                query=query, returned=len(kept), filtered_out=len(raw) - len(allowed))
        return kept

    def get(self, doc_id: str, fetch: Callable[[str], Optional[Document]]) -> Document:
        """Direct fetch by id — the object-level authorisation check.

        Retrieval filters are not enough on their own. An endpoint that loads a document by
        id and returns it, without re-checking the tenant, is the classic broken
        object-level authorisation bug: the search results are scoped, and the detail view
        hands over anything whose id you can guess.
        """
        doc = fetch(doc_id)
        if doc is None or doc.metadata.tenant_id != self.tenant_id:
            # Same response either way, so the error cannot be used to probe for existence.
            raise AccessDenied(f"document '{doc_id}' is not accessible")
        if _RANK[doc.metadata.classification] > _RANK[self.max_classification]:
            raise AccessDenied(f"document '{doc_id}' is not accessible")
        return doc
