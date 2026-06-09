# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Arc A S1 — local unit tests for the work-item → reversing-document builder.

A reversal work-item (012 ``kind=reversal``) posts a **negative-qty return Sales Invoice**
(``is_return=1`` — in ERPNext a credit note IS a Sales Invoice with ``is_return=1``), chosen for
symmetric DP-017 reconciliation against the 1:1 forward SI.

THE CRITICAL CORRECTNESS CONSTRAINT (F-002 forward constraint): the unique provenance index spans
ALL Sales Invoices via ``rt_external_id``. The reversing builder MUST write the reversal
work-item's OWN top-level ``external_id`` into ``rt_external_id`` — NOT ``reversal_of.external_id``
(the original sale's). Writing the original's id would collide with the original SI's unique key
and be FALSELY treated as a dup-recovery. The fixture below makes the work-item ``externalId``
differ from BOTH ``sale.externalId`` AND ``reversalOf.externalId`` so a builder reading either of
the wrong fields fails this test.

Pure dict-transform: no frappe, no ERPNext call. Composes on the forward builder so money
conformance (FR-009) runs once on positive magnitudes; qty/amount are then negated.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting import reversal_builder as rb


# A reversal work-item where the top-level externalId ("POS-9002-RET") is DISTINCT from both
# the sale snapshot's externalId AND reversalOf.externalId (both the original "POS-9001"). This
# fixture design is load-bearing for the F-002 test (see module docstring).
def _reversal_work_item(*, external_id: str = "POS-9002-RET", **overrides) -> c.PostingWorkItem:
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
		"workItemRef": "55555555-5555-4555-8555-555555555555",
		"kind": "reversal",
		"sourceSystem": "pos-pulse",
		"externalId": external_id,
		"payloadHash": "b" * 64,
		"businessDate": "2026-06-05",
		"itemCursor": "cursor-2",
		"reversalOf": {
			"sourceSystem": "pos-pulse",
			"externalId": "POS-9001",  # the ORIGINAL sale id — must NOT be written to rt_external_id
			"reversalKind": "refund",
		},
		"sale": {
			"saleRef": "22222222-2222-4222-8222-222222222222",
			"storeId": "33333333-3333-4333-8333-333333333333",
			"currencyCode": "EGP",
			"posTotal": "230.00",
			"occurredAt": "2026-06-01T10:00:00Z",
			"businessDate": "2026-06-01",  # the ORIGINAL business date — credit note posts on its OWN
			"sourceSystem": "pos-pulse",
			"externalId": "POS-9001",  # the ORIGINAL sale id (snapshot) — must NOT leak into rt_external_id
			"lines": [line],
		},
	}
	wire.update(overrides)
	return c.PostingWorkItem.from_wire(wire)


def _reversal_work_item_two_lines(lines: list[dict]) -> c.PostingWorkItem:
	"""A reversal work-item carrying MULTIPLE sale lines (for the multi-line negation test)."""
	wire = {
		"workItemRef": "55555555-5555-4555-8555-555555555555",
		"kind": "reversal",
		"sourceSystem": "pos-pulse",
		"externalId": "POS-9002-RET",
		"payloadHash": "b" * 64,
		"businessDate": "2026-06-05",
		"itemCursor": "cursor-2",
		"reversalOf": {
			"sourceSystem": "pos-pulse",
			"externalId": "POS-9001",
			"reversalKind": "refund",
		},
		"sale": {
			"saleRef": "22222222-2222-4222-8222-222222222222",
			"storeId": "33333333-3333-4333-8333-333333333333",
			"currencyCode": "EGP",
			"posTotal": "246.50",
			"occurredAt": "2026-06-01T10:00:00Z",
			"businessDate": "2026-06-01",
			"sourceSystem": "pos-pulse",
			"externalId": "POS-9001",
			"lines": lines,
		},
	}
	return c.PostingWorkItem.from_wire(wire)


def _uom(unit: str) -> str:
	mapping = {"each": "Nos"}
	if unit not in mapping:
		from retail_tower_erpnext_connector.connector.posting import builder as b

		raise b.UnmappedUnit(unit)
	return mapping[unit]


def _warehouse(store_id: str) -> dict:
	return {"doctype": "Warehouse", "name": "Main - RT"}


def _customer(store_id: str) -> str:
	return "Walk-in Customer - RT"


def _build(work_item=None, **kw):
	return rb.build_reversing_invoice(
		work_item or _reversal_work_item(),
		uom_for=_uom,
		warehouse_for=_warehouse,
		customer_for=_customer,
		**kw,
	)


class TestF002ProvenanceIdentity:
	def test_rt_external_id_is_work_item_own_external_id_not_original(self):
		# THE HEADLINE TEST (F-002). The reversing doc's rt_external_id MUST be the reversal
		# work-item's OWN top-level externalId ("POS-9002-RET"), NOT the original sale's
		# ("POS-9001", carried in both reversalOf.externalId and the sale snapshot). A builder
		# reading reversal_of.external_id OR sale.external_id would collide with the original SI's
		# unique provenance slot and be falsely treated as dup-recovery.
		wi = _reversal_work_item()
		doc = _build(wi)
		assert doc["rt_external_id"] == "POS-9002-RET"
		assert doc["rt_external_id"] == wi.external_id
		# Explicitly prove neither wrong source was used.
		assert doc["rt_external_id"] != wi.reversal_of.external_id  # "POS-9001"
		assert doc["rt_external_id"] != wi.sale.external_id  # "POS-9001"

	def test_rt_source_system_is_work_item_own(self):
		wi = _reversal_work_item()
		doc = _build(wi)
		assert doc["rt_source_system"] == wi.source_system


class TestNegativeQty:
	def test_qty_is_negated(self):
		# A return Sales Invoice carries NEGATIVE line quantities.
		doc = _build()
		assert doc["items"][0]["qty"] == "-2"

	def test_amount_is_negated(self):
		# amount mirrors qty sign so the credit note totals are negative.
		doc = _build()
		assert doc["items"][0]["amount"] == "-200.00"

	def test_rate_stays_positive(self):
		# ERPNext return semantics: the unit rate stays positive; the qty carries the sign.
		doc = _build()
		assert doc["items"][0]["rate"] == "100.00"

	def test_qty_and_amount_are_strings_not_float(self):
		item = _build()["items"][0]
		for value in (item["qty"], item["amount"], item["rate"]):
			assert isinstance(value, str)
			assert not isinstance(value, float)

	def test_every_line_is_negated_multi_line(self):
		# A single-line fixture would let a bug that negates only items[0] (or copies it) slip
		# through. This work-item carries TWO lines with DISTINCT magnitudes; assert EVERY line's
		# qty AND amount are negated independently (rate stays positive on each).
		two_lines = [
			{
				"lineName": "Item A",
				"unitPrice": "100.00",
				"currencyCode": "EGP",
				"quantity": "2",
				"lineAmount": "200.00",
				"taxAmount": "30.00",
				"unit": "each",
				"erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
			},
			{
				"lineName": "Item B",
				"unitPrice": "5.50",
				"currencyCode": "EGP",
				"quantity": "3",
				"lineAmount": "16.50",
				"taxAmount": "0.00",
				"unit": "each",
				"erpnextItemRef": {"doctype": "Item", "name": "ITEM-B"},
			},
		]
		doc = _build(_reversal_work_item_two_lines(two_lines))
		items = doc["items"]
		assert len(items) == 2
		# Line 0 negated.
		assert items[0]["qty"] == "-2"
		assert items[0]["amount"] == "-200.00"
		assert items[0]["rate"] == "100.00"
		# Line 1 negated INDEPENDENTLY (distinct magnitudes — a copy-of-items[0] bug fails here).
		assert items[1]["qty"] == "-3"
		assert items[1]["amount"] == "-16.50"
		assert items[1]["rate"] == "5.50"


class TestNegateHelper:
	def test_positive_integer_negated(self):
		assert rb._negate("2") == "-2"

	def test_positive_decimal_negated(self):
		assert rb._negate("200.00") == "-200.00"

	def test_already_negative_raises(self):
		# Fail-closed: an already-negative magnitude is a contract violation, NOT a silent
		# double-negation back to a spurious positive.
		with pytest.raises(ValueError):
			rb._negate("-5.00")

	def test_zero_variants_pass_through_unchanged(self):
		for zero in ("0", "0.0", "0.00", "0.000", "0.0000"):
			assert rb._negate(zero) == zero


class TestIsReturnAndReturnAgainst:
	def test_is_return_flag_set(self):
		doc = _build()
		assert doc["is_return"] == 1

	def test_doctype_is_sales_invoice(self):
		# A credit note IS a Sales Invoice with is_return=1 (CHECKPOINT-1 decision).
		doc = _build()
		assert doc["doctype"] == "Sales Invoice"

	def test_return_against_not_resolved_in_pure_layer(self):
		# The pure builder cannot resolve reversal_of -> the original SI's ERPNext docname
		# (that needs a DB hit; the injected signature has no SI-resolver). It emits a standalone
		# is_return=1 credit note; the bench-pending frappe_glue leg sets return_against before
		# insert. ERPNext accepts is_return=1 WITHOUT return_against, so the payload is valid.
		doc = _build()
		assert doc.get("return_against") is None


class TestCardinalityNto1:
	def test_two_reversals_sharing_one_original_get_distinct_rt_external_id(self):
		# Reversal->original is N:1 (successive partial returns). Each reversal work-item has its
		# OWN externalId / reversal key; the forward 1:1 must not bleed in. Two reversals of the
		# same original sale produce DISTINCT rt_external_id.
		doc_a = _build(_reversal_work_item(external_id="POS-9002-RET-A"))
		doc_b = _build(_reversal_work_item(external_id="POS-9002-RET-B"))
		assert doc_a["rt_external_id"] == "POS-9002-RET-A"
		assert doc_b["rt_external_id"] == "POS-9002-RET-B"
		assert doc_a["rt_external_id"] != doc_b["rt_external_id"]
		# ...yet both target the same original (provenance of the reversed sale is shared).
		wi_a = _reversal_work_item(external_id="POS-9002-RET-A")
		wi_b = _reversal_work_item(external_id="POS-9002-RET-B")
		assert wi_a.reversal_of.external_id == wi_b.reversal_of.external_id


class TestResolutionMirrorsForward:
	def test_customer_currency_warehouse_uom_resolution(self):
		doc = _build()
		assert doc["customer"] == "Walk-in Customer - RT"
		assert doc["currency"] == "EGP"
		assert doc["items"][0]["item_code"] == "ITEM-A"
		assert doc["items"][0]["uom"] == "Nos"
		assert doc["items"][0]["warehouse"] == "Main - RT"

	def test_unmapped_unit_propagates(self):
		from retail_tower_erpnext_connector.connector.posting import builder as b

		def _uom_unmapped(unit: str) -> str:
			raise b.UnmappedUnit(unit)

		with pytest.raises(b.UnmappedUnit):
			rb.build_reversing_invoice(
				_reversal_work_item(),
				uom_for=_uom_unmapped,
				warehouse_for=_warehouse,
				customer_for=_customer,
			)

	def test_unmapped_store_propagates(self):
		from retail_tower_erpnext_connector.connector.posting import uom as u

		def _unmapped(store_id: str) -> str:
			raise u.UnmappedStore(store_id)

		with pytest.raises(u.UnmappedStore):
			rb.build_reversing_invoice(
				_reversal_work_item(),
				uom_for=_uom,
				warehouse_for=_warehouse,
				customer_for=_unmapped,
			)


class TestPostingDate:
	def test_credit_note_posts_on_reversal_work_item_business_date(self):
		# The credit note must post on the REVERSAL's own businessDate (its fiscal period), NOT the
		# original sale's snapshot businessDate. The fixture sets work-item businessDate "2026-06-05"
		# vs the sale snapshot's original "2026-06-01".
		doc = _build()
		assert doc["posting_date"] == "2026-06-05"


class TestRejectsSalePost:
	def test_sale_post_work_item_is_rejected(self):
		# build_reversing_invoice is for reversal work-items only; a sale_post must not be built
		# into a credit note (it has no reversal_of and would mis-post).
		sale_post = c.PostingWorkItem.from_wire(
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
					"posTotal": "230.00",
					"occurredAt": "2026-06-01T10:00:00Z",
					"businessDate": "2026-06-01",
					"sourceSystem": "pos-pulse",
					"externalId": "POS-9001",
					"lines": [
						{
							"lineName": "Item A",
							"unitPrice": "100.00",
							"currencyCode": "EGP",
							"quantity": "2",
							"lineAmount": "200.00",
							"unit": "each",
							"erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
						}
					],
				},
			}
		)
		with pytest.raises(ValueError):
			rb.build_reversing_invoice(
				sale_post, uom_for=_uom, warehouse_for=_warehouse, customer_for=_customer
			)
