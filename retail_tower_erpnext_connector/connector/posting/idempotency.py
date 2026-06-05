# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Idempotency replay logic for posting (T040/T042).

Every post is keyed on the 012 O-3 wire anchor ``(sourceSystem, externalId)`` (FR-005): the
same logical sale maps to the same ERPNext document, and a re-offer echoes the existing
``documentRef`` unchanged (Principle IV / Gate G5). The connector introduces NO new
idempotency primitive beyond the 012 contract.

The persistence is abstracted behind :class:`IdempotencyStore` (a Protocol — the repo's
Repository pattern). The concrete Frappe-DocType-backed store is the deferred ``[GATED]``
T020 adapter (its DocType JSON is a forbidden surface, standing-rules §3) and a
⏳ BENCH-VALIDATION concern. This module imports NO frappe.
"""

from __future__ import annotations

from typing import Protocol

from .contracts import ErpnextDocumentRef, PostingWorkItem

Key = tuple[str, str]


class IdempotencyConflict(Exception):
    """The same replay key already maps to a DIFFERENT document (012 409-class conflict).

    Reusing an idempotency key with a different logical outcome is rejected — the connector
    never silently overwrites a recorded posting (Principle IV).
    """

    def __init__(self, key: Key, existing: ErpnextDocumentRef, attempted: ErpnextDocumentRef) -> None:
        super().__init__(
            f"idempotency conflict for {key}: already posted as {existing}, "
            f"attempted {attempted} (409 idempotency_key_conflict)"
        )
        self.key = key
        self.existing = existing
        self.attempted = attempted


class IdempotencyStore(Protocol):
    """Persistence for ``(sourceSystem, externalId) → documentRef``.

    ``record_posted`` MUST raise :class:`IdempotencyConflict` if the key already maps to a
    different ``documentRef`` (re-recording the same ref is a no-op replay)."""

    def get_document_ref(self, key: Key) -> ErpnextDocumentRef | None: ...

    def record_posted(self, key: Key, document_ref: ErpnextDocumentRef) -> None: ...


def key_for(work_item: PostingWorkItem) -> Key:
    """The replay key for a work-item — the 012 O-3 anchor ``(sourceSystem, externalId)``."""
    return work_item.idempotency_key


def replay_guard(store: IdempotencyStore, key: Key) -> ErpnextDocumentRef | None:
    """Return the recorded ``documentRef`` if this key was already posted, else ``None``.

    A non-``None`` result means the caller MUST short-circuit — echo the existing
    ``documentRef`` as an idempotent duplicate ``posted`` and NOT re-build/re-submit.
    """
    return store.get_document_ref(key)
