# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Pure stock-posting policy for stock-moving Sales Invoices (RT-48).

Owner decisions (RT-47 comment 10287; RT-48 comment 10291):

  - **D4 — no guessed batches.** The technical pilot moves stock only for non-batch / non-serial
    Items. ERPNext would otherwise AUTO-PICK a batch/serial on an outward line
    (``auto_create_serial_and_batch_bundle_for_outward`` defaults on) — a guess — so a tracked
    Item on a stock-moving document fails CLOSED (:class:`UnsupportedTrackedItem` → ``validation``).
    Batch/expiry is a separate pharmacy capability (RT-50).
  - **D5 — a full void restores stock exactly once, and only if the sale moved it.** The return
    invoice MIRRORS the original invoice's ``update_stock`` (a legacy ``update_stock=0`` invoice
    gets an accounting-only credit note — never a fabricated stock restoration; ERPNext also refuses
    ``update_stock=1`` against a non-stock original) and references each original line via
    ``sales_invoice_item`` so ERPNext's per-line over-return cap (``StockOverReturnError``) applies.

The frappe glue only READS the Item flags / original invoice rows and calls these functions.
This module imports NO frappe and never mutates its inputs.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from decimal import Decimal


class UnsupportedTrackedItem(Exception):
	"""A batch- or serial-tracked Item on a stock-moving document (RT-47 D4 fail-closed)."""

	def __init__(self, item_codes: Sequence[str]) -> None:
		super().__init__(
			f"stock posting does not support batch/serial-tracked Item(s) {', '.join(item_codes)} "
			"(V1 technical pilot: non-batch, non-serial Items only; the connector never guesses a batch)"
		)
		self.item_codes = tuple(item_codes)


class ReturnLineMismatch(Exception):
	"""A void's lines do not line up 1:1 with the original invoice rows (fail-closed)."""


def tracking_item_codes(doc: Mapping[str, object]) -> list[str]:
	"""The distinct ``item_code``s on ``doc`` in first-seen order (the Item-flag lookup set)."""
	seen: list[str] = []
	for item in doc.get("items") or []:  # type: ignore[union-attr]
		code = item["item_code"]
		if code not in seen:
			seen.append(code)
	return seen


def assert_no_tracked_items(doc: Mapping[str, object], tracking: Mapping[str, Mapping[str, object]]) -> None:
	"""Raise :class:`UnsupportedTrackedItem` if a stock-moving ``doc`` carries a batch/serial Item.

	``tracking`` maps ``item_code`` → ``{has_batch_no, has_serial_no}`` (read by the glue from the
	ERPNext Item master). A document that does not move stock (``update_stock`` falsy) is not
	checked — no Serial and Batch Bundle is involved. An Item absent from ``tracking`` is left to
	ERPNext's own link validation (it rejects an unknown Item on insert).
	"""
	if not doc.get("update_stock"):
		return
	tracked = [code for code in tracking_item_codes(doc) if _is_tracked(tracking.get(code))]
	if tracked:
		raise UnsupportedTrackedItem(tracked)


def _is_tracked(flags: Mapping[str, object] | None) -> bool:
	"""True if an Item's master flags mark it batch- or serial-tracked (absent Item → False)."""
	if not flags:
		return False
	return bool(int(flags.get("has_batch_no") or 0) or int(flags.get("has_serial_no") or 0))


def link_void_to_original(
	doc: Mapping[str, object],
	*,
	original_update_stock: int,
	original_items: Sequence[Mapping[str, object]],
) -> dict:
	"""Return a copy of the void return ``doc`` mirrored onto and linked to its original invoice.

	- ``update_stock`` := the original's (never restore stock the sale did not move).
	- each return line is paired with the original row at the same position (rows ordered by
	  ``idx``; DP2 emits sale and reversal lines in the same ``ORDER BY sale_lines.id``), checked
	  for ``item_code`` and exact quantity (:func:`_check_pair`), then gets ``sales_invoice_item``
	  and the ORIGINAL row's warehouse, so stock goes back where the sale took it from even if the
	  store→warehouse map changed since (Codex P1, PR #42). Any mismatch raises
	  :class:`ReturnLineMismatch`.
	"""
	if not doc.get("is_return"):
		raise ValueError("link_void_to_original expects a return (is_return=1) document")

	out = copy.deepcopy(dict(doc))
	lines = out.get("items") or []
	rows = sorted(original_items, key=lambda r: int(r["idx"]))  # type: ignore[arg-type]
	if len(lines) != len(rows):
		raise ReturnLineMismatch(
			f"void carries {len(lines)} line(s) but the original invoice has {len(rows)} row(s)"
		)

	for pos, (line, row) in enumerate(zip(lines, rows, strict=True), start=1):
		_check_pair(pos, line, row)
		line["sales_invoice_item"] = row["name"]
		if row.get("warehouse"):
			line["warehouse"] = row["warehouse"]

	out["update_stock"] = 1 if int(original_update_stock or 0) else 0
	return out


def _check_pair(pos: int, line: Mapping[str, object], row: Mapping[str, object]) -> None:
	"""Fail closed unless a void line matches its original row's Item and exact sold quantity.

	A full void restores EXACTLY the sold quantity; both sides are compared as :class:`Decimal`
	built from their string form (the DB row's qty is a float), never float-vs-string.
	"""
	if line["item_code"] != row["item_code"]:
		raise ReturnLineMismatch(
			f"void line {pos} item {line['item_code']!r} != original row item {row['item_code']!r}"
		)
	returned = abs(Decimal(str(line["qty"])))
	sold = abs(Decimal(str(row["qty"])))
	if returned != sold:
		raise ReturnLineMismatch(
			f"void line {pos} quantity {returned} != original sold quantity {sold} (full void only)"
		)
