# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""T040/T042 — local unit tests for idempotency replay logic.

The store is abstracted behind :class:`IdempotencyStore` (Protocol); tests use an in-memory
fake. The concrete Frappe-DocType-backed store is the deferred [GATED] T020 adapter and a
⏳ BENCH-VALIDATION concern. Replay key = (sourceSystem, externalId) — the 012 O-3 anchor.
No frappe here.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting import idempotency as idem


class InMemoryStore:
    """A fake implementing the IdempotencyStore Protocol."""

    def __init__(self):
        self._posted: dict[tuple[str, str], c.ErpnextDocumentRef] = {}

    def get_document_ref(self, key: tuple[str, str]) -> c.ErpnextDocumentRef | None:
        return self._posted.get(key)

    def record_posted(self, key: tuple[str, str], document_ref: c.ErpnextDocumentRef) -> None:
        existing = self._posted.get(key)
        if existing is not None and existing != document_ref:
            raise idem.IdempotencyConflict(key, existing, document_ref)
        self._posted[key] = document_ref


KEY = ("pos-pulse", "POS-9001")
DOC = c.ErpnextDocumentRef("Sales Invoice", "ACC-SINV-0001")


class TestReplayGuard:
    def test_first_post_is_not_a_replay(self):
        store = InMemoryStore()
        existing = idem.replay_guard(store, KEY)
        assert existing is None

    def test_already_posted_short_circuits_to_recorded_document_ref(self):
        # T040: same (sourceSystem, externalId) → return the existing documentRef,
        # builder/submit not re-entered.
        store = InMemoryStore()
        store.record_posted(KEY, DOC)
        existing = idem.replay_guard(store, KEY)
        assert existing == DOC

    def test_record_then_replay_echoes_same_ref(self):
        store = InMemoryStore()
        store.record_posted(KEY, DOC)
        # A re-offer of the same key echoes the SAME documentRef (Principle IV / O-3).
        assert idem.replay_guard(store, KEY) == DOC


class TestAckReplay:
    def test_same_logical_outcome_replays_deterministically(self):
        # T042: recording the same (key, documentRef) twice is idempotent — no error.
        store = InMemoryStore()
        store.record_posted(KEY, DOC)
        store.record_posted(KEY, DOC)  # replay — must not raise
        assert store.get_document_ref(KEY) == DOC

    def test_different_outcome_for_same_key_conflicts(self):
        # T042: a DIFFERENT documentRef for the same key → 409-class conflict.
        store = InMemoryStore()
        store.record_posted(KEY, DOC)
        other = c.ErpnextDocumentRef("Sales Invoice", "ACC-SINV-9999")
        with pytest.raises(idem.IdempotencyConflict):
            store.record_posted(KEY, other)


class TestKeyDerivation:
    def test_key_comes_from_work_item_anchor(self):
        wi = _work_item()
        assert idem.key_for(wi) == ("pos-pulse", "POS-9001")


def _work_item() -> c.PostingWorkItem:
    return c.PostingWorkItem.from_wire(
        {
            "workItemRef": "11111111-1111-4111-8111-111111111111",
            "kind": "sale_post",
            "sourceSystem": "pos-pulse",
            "externalId": "POS-9001",
            "payloadHash": "a" * 64,
            "businessDate": "2026-06-01",
            "itemCursor": "cursor-1",
            "sale": {
                "saleRef": "22222222-2222-4222-8222-222222222222",
                "storeId": "33333333-3333-4333-8333-333333333333",
                "currencyCode": "EGP",
                "posTotal": "100.00",
                "occurredAt": "2026-06-01T10:00:00Z",
                "businessDate": "2026-06-01",
                "sourceSystem": "pos-pulse",
                "externalId": "POS-9001",
                "lines": [
                    {
                        "lineName": "Item A",
                        "unitPrice": "100.00",
                        "currencyCode": "EGP",
                        "quantity": "1",
                        "lineAmount": "100.00",
                        "unit": "each",
                        "erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
                    }
                ],
            },
        }
    )
