# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-48 — local unit tests for the pure stock-posting policy (no frappe).

Owner decisions (RT-47 comment 10287, RT-48 comment 10291):
  - D4: the technical pilot moves stock only for non-batch / non-serial items. ERPNext would
    otherwise AUTO-PICK a batch (``auto_create_serial_and_batch_bundle_for_outward`` defaults on),
    i.e. guess one, so a batch/serial line on a stock-moving document fails CLOSED.
  - D5: a full void's return invoice mirrors the ORIGINAL invoice's ``update_stock`` (a legacy
    update_stock=0 invoice never fabricates a stock restoration) and references each original line
    via ``sales_invoice_item`` so ERPNext's per-line over-return cap applies.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import stock_policy as sp


def _doc(*, update_stock=1, is_return=0, items=None):
	return {
		"doctype": "Sales Invoice",
		"update_stock": update_stock,
		"is_return": is_return,
		"items": items
		or [
			{"item_code": "ITEM-A", "qty": "-2" if is_return else "2"},
			{"item_code": "ITEM-B", "qty": "-1.5" if is_return else "1.5"},
		],
	}


_PLAIN = {"has_batch_no": 0, "has_serial_no": 0}


class TestTrackedItemGuard:
	def test_plain_items_pass(self):
		sp.assert_no_tracked_items(_doc(), {"ITEM-A": _PLAIN, "ITEM-B": _PLAIN})

	def test_batch_item_on_stock_moving_doc_fails_closed(self):
		tracking = {"ITEM-A": _PLAIN, "ITEM-B": {"has_batch_no": 1, "has_serial_no": 0}}
		with pytest.raises(sp.UnsupportedTrackedItem) as exc:
			sp.assert_no_tracked_items(_doc(), tracking)
		assert "ITEM-B" in str(exc.value)

	def test_serial_item_on_stock_moving_doc_fails_closed(self):
		tracking = {"ITEM-A": {"has_batch_no": 0, "has_serial_no": 1}, "ITEM-B": _PLAIN}
		with pytest.raises(sp.UnsupportedTrackedItem):
			sp.assert_no_tracked_items(_doc(), tracking)

	def test_non_stock_moving_doc_is_not_checked(self):
		# A refund credit note / legacy-mirrored return posts update_stock=0: no Serial and Batch
		# Bundle is involved, so batch flags are irrelevant there.
		tracking = {"ITEM-A": {"has_batch_no": 1, "has_serial_no": 1}, "ITEM-B": _PLAIN}
		sp.assert_no_tracked_items(_doc(update_stock=0), tracking)

	def test_tracking_item_codes_lists_each_code_once_in_order(self):
		items = [
			{"item_code": "A", "qty": "1"},
			{"item_code": "A", "qty": "2"},
			{"item_code": "B", "qty": "1"},
		]
		assert sp.tracking_item_codes(_doc(items=items)) == ["A", "B"]


def _original_rows():
	# Shaped like frappe.get_all("Sales Invoice Item", fields=[name, item_code, qty, idx]): qty is a
	# FLOAT from the DB, so the policy must compare it as an exact decimal, never float-vs-string.
	return [
		{"name": "row-1", "item_code": "ITEM-A", "qty": 2.0, "idx": 1},
		{"name": "row-2", "item_code": "ITEM-B", "qty": 1.5, "idx": 2},
	]


def _link(doc=None, *, original_update_stock=1, original_disable_rounded_total=1, original_items=None):
	return sp.link_void_to_original(
		doc or _doc(is_return=1),
		original_update_stock=original_update_stock,
		original_disable_rounded_total=original_disable_rounded_total,
		original_items=_original_rows() if original_items is None else original_items,
	)


class TestVoidLinkage:
	def test_mirrors_a_stock_moving_original(self):
		assert _link(original_update_stock=1)["update_stock"] == 1

	def test_legacy_original_never_fabricates_stock_restoration(self):
		assert _link(original_update_stock=0)["update_stock"] == 0

	def test_mirrors_an_unrounded_original(self):
		# RT-80: a sale posted with the fix carries disable_rounded_total=1; its void does too.
		assert _link(original_disable_rounded_total=1)[
			"disable_rounded_total"
		] == 1

	def test_legacy_rounded_original_is_reversed_with_its_own_rounding(self):
		# RT-80 (Codex P2, PR #47): a pre-fix sale posted 10.49 as AR 10.00 + Round Off 0.49. An
		# unrounded -10.49 void would leave a -0.49 customer credit and never reverse the Round Off
		# (rt9 bench T4). Mirroring the original's rounding makes the void net to exactly zero.
		assert _link(original_disable_rounded_total=0)[
			"disable_rounded_total"
		] == 0

	def test_each_line_references_its_original_row_by_position(self):
		doc = _link()
		assert [i["sales_invoice_item"] for i in doc["items"]] == ["row-1", "row-2"]

	def test_original_rows_are_matched_in_idx_order(self):
		doc = _link(original_items=list(reversed(_original_rows())))  # DB rows may arrive unordered
		assert [i["sales_invoice_item"] for i in doc["items"]] == ["row-1", "row-2"]

	def test_does_not_mutate_the_input_doc(self):
		src = _doc(is_return=1)
		_link(src, original_update_stock=0)
		assert src["update_stock"] == 1
		assert "sales_invoice_item" not in src["items"][0]

	def test_line_count_mismatch_fails_closed(self):
		with pytest.raises(sp.ReturnLineMismatch):
			_link(original_items=_original_rows()[:1])

	def test_item_code_mismatch_fails_closed(self):
		rows = _original_rows()
		rows[1] = {**rows[1], "item_code": "ITEM-Z"}
		with pytest.raises(sp.ReturnLineMismatch):
			_link(original_items=rows)

	def test_quantity_mismatch_fails_closed(self):
		# A full void restores EXACTLY the sold quantity — compared as exact decimals.
		rows = _original_rows()
		rows[0] = {**rows[0], "qty": 3.0}
		with pytest.raises(sp.ReturnLineMismatch):
			_link(original_items=rows)

	def test_each_line_restores_stock_to_the_original_rows_warehouse(self):
		# Codex P1 (PR #42): if the store→warehouse map changed between the sale and its void, the
		# builder stamps the CURRENT mapped warehouse. The void must restore stock where the sale
		# took it from, otherwise the depleted warehouse is never credited.
		rows = [
			{**_original_rows()[0], "warehouse": "Old Store - RT"},
			{**_original_rows()[1], "warehouse": "Old Store - RT"},
		]
		doc = _doc(is_return=1)
		for item in doc["items"]:
			item["warehouse"] = "New Store - RT"
		out = _link(doc, original_items=rows)
		assert [i["warehouse"] for i in out["items"]] == ["Old Store - RT", "Old Store - RT"]

	def test_rejects_a_non_return_document(self):
		with pytest.raises(ValueError):
			_link(_doc(is_return=0))
