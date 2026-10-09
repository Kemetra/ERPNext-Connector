# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt
"""RT-331 — verify an EXISTING ERP document against the work item's frozen resolution (pure).

The ERP Integration baseline: "matching provenance alone proves identity candidate, not
correctness". On a replay-guard or duplicate-recovery hit the connector compares the existing
invoice with the frozen refs before acking ``posted``. A mismatch (or a document that is not
submitted) means ``reconciliation_required``; ``None`` means the document matches.
"""

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting.resolution_check import (
	InvoiceLine,
	InvoiceSnapshot,
	check_existing,
)

_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _line(ref, item):
	return {
		"lineRef": ref,
		"lineName": item,
		"unitPrice": "10.00",
		"currencyCode": "EGP",
		"quantity": "1",
		"lineAmount": "10.00",
		"unit": "each",
		"erpnextItemRef": {"doctype": "Item", "name": item},
	}


def _item(kind="sale_post", warehouse="WH-F"):
	sale = {
		"saleRef": "22222222-2222-4222-8222-222222222222",
		"storeId": "33333333-3333-4333-8333-333333333333",
		"currencyCode": "EGP",
		"posTotal": "20.00",
		"occurredAt": "2026-06-01T10:00:00Z",
		"businessDate": "2026-06-01",
		"sourceSystem": "pos-pulse",
		"externalId": "POS-1",
		"lines": [_line(_A, "ITEM-A"), _line(_B, "ITEM-B")],
	}
	if warehouse is not None:
		sale["warehouseRef"] = {"doctype": "Warehouse", "name": warehouse}
	wire = {
		"workItemRef": "11111111-1111-4111-8111-111111111111",
		"kind": kind,
		"sourceSystem": "pos-pulse",
		"externalId": "POS-1",
		"payloadHash": "a" * 64,
		"businessDate": "2026-06-01",
		"itemCursor": "7",
		"resolutionVersion": 1,
		"sale": sale,
	}
	if kind == "reversal":
		wire["reversalOf"] = {
			"sourceSystem": "pos-pulse",
			"externalId": "POS-1",
			"reversalKind": "void",
			"recordedAt": "2026-06-05T09:30:00Z",
			"businessDate": "2026-06-05",
		}
	return c.PostingWorkItem.from_wire(wire)


def _invoice(*lines, docstatus=1):
	return InvoiceSnapshot(docstatus=docstatus, items=tuple(InvoiceLine(*line) for line in lines))


class TestSalePost:
	def test_a_matching_invoice_passes(self):
		assert check_existing(_item(), _invoice(("ITEM-A", "WH-F", _A), ("ITEM-B", "WH-F", _B))) is None

	def test_a_different_item_on_a_frozen_line_is_a_mismatch(self):
		assert check_existing(_item(), _invoice(("ITEM-Z", "WH-F", _A), ("ITEM-B", "WH-F", _B)))

	def test_a_different_warehouse_is_a_mismatch(self):
		assert check_existing(_item(), _invoice(("ITEM-A", "WH-X", _A), ("ITEM-B", "WH-F", _B)))

	def test_no_frozen_warehouse_means_the_warehouse_is_not_compared(self):
		item = _item(warehouse=None)
		assert check_existing(item, _invoice(("ITEM-A", "WH-X", _A), ("ITEM-B", "WH-X", _B))) is None

	def test_a_missing_frozen_line_is_a_mismatch(self):
		assert check_existing(_item(), _invoice(("ITEM-A", "WH-F", _A)))

	def test_an_unknown_line_ref_is_a_mismatch(self):
		other = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
		assert check_existing(_item(), _invoice(("ITEM-A", "WH-F", _A), ("ITEM-B", "WH-F", other)))

	def test_without_line_refs_the_item_codes_must_match_as_a_multiset(self):
		assert check_existing(_item(), _invoice(("ITEM-B", "WH-F", None), ("ITEM-A", "WH-F", None))) is None
		assert check_existing(_item(), _invoice(("ITEM-A", "WH-F", None), ("ITEM-A", "WH-F", None)))

	def test_a_document_that_is_not_submitted_is_a_mismatch(self):
		assert check_existing(_item(), _invoice(("ITEM-A", "WH-F", _A), ("ITEM-B", "WH-F", _B), docstatus=2))


class TestReversal:
	def test_a_subset_of_the_frozen_lines_passes(self):
		assert check_existing(_item("reversal"), _invoice(("ITEM-A", "WH-F", _A))) is None

	def test_a_different_item_is_a_mismatch(self):
		assert check_existing(_item("reversal"), _invoice(("ITEM-Z", "WH-F", _A)))
