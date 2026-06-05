# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""T030/T033/T034 — local unit tests for the work-item → Sales-Invoice builder.

Pure dict-transform: it APPLIES each line's pre-resolved erpnextItemRef (no resolution),
represents money as exact-decimal strings (never float), carries businessDate → posting_date,
and addresses every ERPNext doc generically as {doctype, name}. No frappe, no ERPNext call.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import builder as b
from retail_tower_erpnext_connector.connector.posting import contracts as c


def _work_item(**overrides) -> c.PostingWorkItem:
    line = {
        "lineName": "Item A",
        "unitPrice": "100.00",
        "currencyCode": "EGP",
        "quantity": "2",
        "lineAmount": "200.00",
        "taxAmount": "30.00",
        "unit": "each",
        "erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
    }
    wire = {
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
            "posTotal": "230.00",
            "occurredAt": "2026-06-01T10:00:00Z",
            "businessDate": "2026-06-01",
            "sourceSystem": "pos-pulse",
            "externalId": "POS-9001",
            "lines": [line],
        },
    }
    wire.update(overrides)
    return c.PostingWorkItem.from_wire(wire)


# A trivial UOM resolver for the builder under test: maps "each" → "Nos".
def _uom(unit: str) -> str:
    mapping = {"each": "Nos"}
    if unit not in mapping:
        raise b.UnmappedUnit(unit)
    return mapping[unit]


def _warehouse(store_id: str) -> dict:
    # The DP2-pre-resolved warehouse identity, applied generically (rider R5).
    return {"doctype": "Warehouse", "name": "Main - RT"}


class TestBuilderHappyPath:
    def test_builds_one_sales_invoice_doc(self):
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        assert doc["doctype"] == "Sales Invoice"
        assert len(doc["items"]) == 1

    def test_applies_erpnext_item_ref_as_item_code(self):
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        # T030: the line references the APPLIED Item by name; no resolution happened.
        assert doc["items"][0]["item_code"] == "ITEM-A"

    def test_carries_business_date_as_posting_date(self):
        # T033: businessDate → posting_date (never the connector's post-time).
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        assert doc["posting_date"] == "2026-06-01"

    def test_carries_provenance(self):
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        assert doc["rt_source_system"] == "pos-pulse"
        assert doc["rt_external_id"] == "POS-9001"

    def test_applies_uom_and_warehouse(self):
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        assert doc["items"][0]["uom"] == "Nos"
        assert doc["items"][0]["warehouse"] == "Main - RT"


class TestBuilderMoneyFidelity:
    def test_money_is_exact_decimal_strings_not_float(self):
        # T033: every monetary field stays an exact-decimal string; no float anywhere.
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        item = doc["items"][0]
        assert item["rate"] == "100.00"
        assert item["amount"] == "200.00"
        assert item["qty"] == "2"
        for value in (item["rate"], item["amount"], item["qty"]):
            assert isinstance(value, str)
            assert not isinstance(value, float)

    def test_currency_code_present(self):
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        assert doc["currency"] == "EGP"


class TestBuilderSelfValidatesMoney:
    def test_builder_output_is_money_conformant(self):
        # F-007: build_sales_invoice enforces money conformance on its OWN output before
        # returning — FR-009 is enforced in the path, not only by a separately-callable check.
        doc = b.build_sales_invoice(_work_item(), uom_for=_uom, warehouse_for=_warehouse)
        # The builder must have validated; re-asserting here proves the contract holds.
        from retail_tower_erpnext_connector.connector.posting import uom as u

        u.assert_money_conformance(doc)

    def test_builder_rejects_a_non_decimal_money_value(self):
        # If a line's money arrives as a non-DecimalAmount string (e.g. upstream "100.0" is
        # fine, but "100.123456" is not), the builder must fail closed, not emit it.
        wi = _work_item(
            sale={
                "saleRef": "22222222-2222-4222-8222-222222222222",
                "storeId": "33333333-3333-4333-8333-333333333333",
                "currencyCode": "EGP",
                "posTotal": "230.00",
                "occurredAt": "2026-06-01T10:00:00Z",
                "businessDate": "2026-06-01",
                "sourceSystem": "pos-pulse",
                "externalId": "POS-9001",
                "lines": [
                    {
                        "lineName": "Item A",
                        "unitPrice": "100.123456",  # 6 fractional digits — not a DecimalAmount
                        "currencyCode": "EGP",
                        "quantity": "1",
                        "lineAmount": "100.123456",
                        "unit": "each",
                        "erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
                    }
                ],
            }
        )
        from retail_tower_erpnext_connector.connector.posting import uom as u

        with pytest.raises(u.MoneyConformanceError):
            b.build_sales_invoice(wi, uom_for=_uom, warehouse_for=_warehouse)


class TestBuilderFailClosed:
    def test_missing_erpnext_item_ref_is_rejected_at_parse(self):
        # T034: an offered line lacking erpnextItemRef can't even parse into a SaleLine
        # (MissingErpnextItemRef) — it never reaches the builder as a partial doc.
        bad_line = {
            "lineName": "Item A",
            "unitPrice": "100.00",
            "currencyCode": "EGP",
            "quantity": "1",
            "lineAmount": "100.00",
            "unit": "each",
        }
        with pytest.raises(c.MissingErpnextItemRef):
            c.SaleLine.from_wire(bad_line)

    def test_unmapped_unit_raises_unmapped_unit(self):
        # T034/T070 seam: an unmapped unit fails closed (caller maps → validation).
        wi = _work_item()

        def _uom_unmapped(unit: str) -> str:
            raise b.UnmappedUnit(unit)

        with pytest.raises(b.UnmappedUnit):
            b.build_sales_invoice(wi, uom_for=_uom_unmapped, warehouse_for=_warehouse)

    def test_builder_never_resolves_item_identity(self):
        # The builder takes erpnextItemRef as-is; there is no resolution hook to pass.
        import inspect

        sig = inspect.signature(b.build_sales_invoice)
        # Only uom_for + warehouse_for are injected — NO item-resolver parameter exists.
        assert "resolve" not in str(sig).lower()
        assert "item_for" not in sig.parameters
