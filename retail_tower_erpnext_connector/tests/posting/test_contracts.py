# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""T010 — local unit tests for the 012 posting-feed work-item DTOs.

These assert the connector's read-models mirror the fixed, DP2-owned 012
`posting-feed.yaml` (1.1.0-draft) 1:1, and enforce the apply-only invariant
(every offered SaleLine carries a resolved `erpnextItemRef` — rider R2).

The module under test imports NO frappe (pure-Python core); these run locally.
"""

import dataclasses

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c


# A minimal-but-complete wire work-item per the 012 SaleLine/Sale/PostingWorkItem
# required sets (posting-feed.yaml).
def _wire_work_item() -> dict:
    return {
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
            "posTotal": "115.00",
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
                    "taxAmount": "15.00",
                    "unit": "each",
                    "erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
                    "tenantProductRef": "44444444-4444-4444-8444-444444444444",
                }
            ],
        },
    }


class TestErpnextItemRef:
    def test_parses_doctype_and_name(self):
        ref = c.ErpnextItemRef.from_wire({"doctype": "Item", "name": "ITEM-A"})
        assert ref.doctype == "Item"
        assert ref.name == "ITEM-A"

    def test_is_frozen(self):
        ref = c.ErpnextItemRef(doctype="Item", name="ITEM-A")
        assert dataclasses.is_dataclass(ref)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ref.name = "MUTATED"  # type: ignore[misc]

    def test_doctype_must_be_item(self):
        # 012: ErpnextItemRef.doctype is const "Item".
        with pytest.raises(ValueError):
            c.ErpnextItemRef.from_wire({"doctype": "Customer", "name": "X"})


class TestSaleLine:
    def test_parses_all_fields(self):
        line = c.SaleLine.from_wire(_wire_work_item()["sale"]["lines"][0])
        assert line.line_name == "Item A"
        assert line.unit_price == "100.00"
        assert line.quantity == "1"
        assert line.line_amount == "100.00"
        assert line.tax_amount == "15.00"
        assert line.unit == "each"
        assert line.erpnext_item_ref.name == "ITEM-A"
        assert line.tenant_product_ref == "44444444-4444-4444-8444-444444444444"

    def test_erpnext_item_ref_is_required(self):
        # rider R2: every OFFERED line carries a resolved erpnextItemRef.
        bad = dict(_wire_work_item()["sale"]["lines"][0])
        del bad["erpnextItemRef"]
        with pytest.raises(c.MissingErpnextItemRef):
            c.SaleLine.from_wire(bad)

    def test_tenant_product_ref_optional_for_ad_hoc(self):
        line_wire = dict(_wire_work_item()["sale"]["lines"][0])
        line_wire["tenantProductRef"] = None
        line = c.SaleLine.from_wire(line_wire)
        assert line.tenant_product_ref is None
        # ...but erpnextItemRef is still applied (R4: ad-hoc still needs a mapping).
        assert line.erpnext_item_ref.name == "ITEM-A"


class TestPostingWorkItem:
    def test_parses_header_and_sale(self):
        wi = c.PostingWorkItem.from_wire(_wire_work_item())
        assert wi.work_item_ref == "11111111-1111-4111-8111-111111111111"
        assert wi.kind == "sale_post"
        assert wi.source_system == "pos-pulse"
        assert wi.external_id == "POS-9001"
        assert wi.payload_hash == "a" * 64
        assert wi.business_date == "2026-06-01"
        assert wi.sale.currency_code == "EGP"
        assert len(wi.sale.lines) == 1

    def test_idempotency_key_is_source_system_and_external_id(self):
        wi = c.PostingWorkItem.from_wire(_wire_work_item())
        # O-3 wire idempotency anchor (forward sale_post — UNCHANGED).
        assert wi.idempotency_key == ("pos-pulse", "POS-9001")

    def test_idempotency_key_fails_closed_for_reversal(self):
        # #28 guard: a reversal's top-level externalId is the ORIGINAL sale's id, so
        # (sourceSystem, externalId) is the PRE-FIX buggy anchor. idempotency_key must REFUSE to
        # hand it back — reversals key via idempotency.key_for/provenance_id (on workItemRef).
        wire = _wire_work_item()
        wire["kind"] = "reversal"
        wire["reversalOf"] = {
            "sourceSystem": "pos-pulse",
            "externalId": "POS-9001",
            "reversalKind": "refund",
        }
        wi = c.PostingWorkItem.from_wire(wire)
        with pytest.raises(ValueError, match="forward sale_post anchor only"):
            _ = wi.idempotency_key

    def test_reversal_carries_reversal_ref(self):
        wire = _wire_work_item()
        wire["kind"] = "reversal"
        wire["reversalOf"] = {
            "sourceSystem": "pos-pulse",
            "externalId": "POS-9001",
            "reversalKind": "refund",
        }
        wi = c.PostingWorkItem.from_wire(wire)
        assert wi.kind == "reversal"
        assert wi.reversal_of is not None
        assert wi.reversal_of.reversal_kind == "refund"

    def test_sale_post_has_no_reversal_ref(self):
        wi = c.PostingWorkItem.from_wire(_wire_work_item())
        assert wi.reversal_of is None

    def test_empty_lines_is_rejected(self):
        # F-012: 012 Sale.lines is minItems: 1 — an empty lines array must raise.
        wire = _wire_work_item()
        wire["sale"]["lines"] = []
        with pytest.raises(ValueError):
            c.PostingWorkItem.from_wire(wire)


class TestOutcomeAndReason:
    def test_posted_outcome_carries_document_ref(self):
        ack = c.OutcomeAckRequest.posted(
            c.ErpnextDocumentRef(doctype="Sales Invoice", name="ACC-SINV-0001")
        )
        assert ack.outcome == "posted"
        assert ack.document_ref.name == "ACC-SINV-0001"
        assert ack.reason is None

    def test_permanently_rejected_carries_reason(self):
        ack = c.OutcomeAckRequest.permanently_rejected(
            c.RejectionReason(category="validation", message="unmapped unit")
        )
        assert ack.outcome == "permanently_rejected"
        assert ack.reason.category == "validation"
        assert ack.document_ref is None

    def test_failed_transient_has_neither(self):
        ack = c.OutcomeAckRequest.failed_transient()
        assert ack.outcome == "failed_transient"
        assert ack.document_ref is None
        assert ack.reason is None

    def test_rejection_category_must_be_in_closed_set(self):
        # 012 RejectionReason.category closed set — no new wire reason invented.
        with pytest.raises(ValueError):
            c.RejectionReason(category="unmapped_uom", message="x")

    def test_to_wire_round_trips_posted(self):
        ack = c.OutcomeAckRequest.posted(
            c.ErpnextDocumentRef(doctype="Sales Invoice", name="ACC-SINV-0001")
        )
        wire = ack.to_wire()
        assert wire["outcome"] == "posted"
        assert wire["documentRef"] == {"doctype": "Sales Invoice", "name": "ACC-SINV-0001"}
        assert "reason" not in wire or wire["reason"] is None
