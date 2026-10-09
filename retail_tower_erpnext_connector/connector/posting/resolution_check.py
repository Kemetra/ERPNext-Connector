# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt
"""RT-331 — verify an EXISTING ERP document against a work item's frozen resolution (pure).

ERP Integration baseline: "matching provenance alone proves identity candidate, not correctness".
When the replay guard or the duplicate-provenance recovery finds an invoice already posted for this
work item, the connector compares it with the frozen resolution Backend-Core sent (012 1.6.0-draft,
Backend-Core RT-332) before acking ``posted``:

* the document must be submitted (``docstatus == 1``);
* when ``sale.warehouseRef`` is frozen, every invoice item must carry that warehouse;
* items stamped with ``rt_line_ref`` must match the frozen line's ERP item by identity. A
  ``sale_post`` must cover exactly the frozen lines; a ``reversal`` (return / credit note) carries a
  subset of them;
* items without ``rt_line_ref`` (documents from before line stamping) are compared by item code as a
  multiset against the required lines no stamped item covered plus the sale lines that carry no
  ``lineRef`` (a return requires only the lines it names).

``check_existing`` returns ``None`` when the document matches, otherwise a short human-readable reason
(no credentials, no ERPNext internals) for the ``reconciliation_required`` ack. Reading the invoice is
the glue's job; this module never imports frappe.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .contracts import PostingWorkItem


@dataclass(frozen=True)
class InvoiceLine:
	"""One Sales Invoice Item as read back from ERPNext."""

	item_code: str
	warehouse: str | None
	line_ref: str | None


@dataclass(frozen=True)
class InvoiceSnapshot:
	"""The parts of an existing Sales Invoice the frozen resolution is checked against."""

	docstatus: int
	items: tuple[InvoiceLine, ...]


def check_existing(work_item: PostingWorkItem, invoice: InvoiceSnapshot) -> str | None:
	"""``None`` when ``invoice`` matches the work item's frozen resolution, else the mismatch reason."""
	if invoice.docstatus != 1:
		return f"existing document is not submitted (docstatus {invoice.docstatus})"
	return _warehouse_mismatch(work_item, invoice) or _item_mismatch(work_item, invoice)


def _warehouse_mismatch(work_item: PostingWorkItem, invoice: InvoiceSnapshot) -> str | None:
	# Only a forward sale is held to the frozen warehouse: a reversal deliberately takes the
	# ORIGINAL invoice rows' warehouses (link_void_to_original / link_return_to_original).
	frozen = work_item.sale.warehouse_ref
	if work_item.kind != "sale_post" or frozen is None:
		return None
	for line in invoice.items:
		if line.warehouse != frozen["name"]:
			return f"existing line warehouse {line.warehouse!r} is not the frozen {frozen['name']!r}"
	return None


def _required_lines(work_item: PostingWorkItem) -> list[str]:
	"""The frozen line refs the document must carry: a return's returned lines, else every sale line."""
	if _is_return(work_item):
		return [line.line_ref for line in work_item.reversal_of.return_lines]
	return [line.line_ref for line in work_item.sale.lines if line.line_ref]


def _item_mismatch(work_item: PostingWorkItem, invoice: InvoiceSnapshot) -> str | None:
	frozen = {line.line_ref: line.erpnext_item_ref.name for line in work_item.sale.lines if line.line_ref}
	required = _required_lines(work_item)
	stamped = [line for line in invoice.items if line.line_ref is not None]
	mismatch = _stamped_mismatch(frozen, required, stamped)
	if mismatch is not None:
		return mismatch
	expected = _unstamped_expected(work_item, frozen, required, stamped)
	actual = Counter(line.item_code for line in invoice.items if line.line_ref is None)
	if actual != expected:
		return f"existing item codes {sorted(actual)} do not match the frozen {sorted(expected)}"
	return None


def _unstamped_expected(
	work_item: PostingWorkItem, frozen: dict[str, str], required: list[str], stamped: list[InvoiceLine]
) -> Counter:
	"""The item codes the UNSTAMPED rows must account for.

	That is the required lines no stamped row covered, plus every sale line without a ``lineRef``
	(a legacy line can only be matched by item code). A return names its lines by ref, so it never
	requires an unreferenced line.
	"""
	covered = {line.line_ref for line in stamped}
	expected = Counter(frozen[ref] for ref in required if ref not in covered and ref in frozen)
	if not _is_return(work_item):
		expected.update(line.erpnext_item_ref.name for line in work_item.sale.lines if not line.line_ref)
	return expected


def _is_return(work_item: PostingWorkItem) -> bool:
	reversal = work_item.reversal_of
	return reversal is not None and reversal.reversal_kind == "return"


def _stamped_mismatch(frozen: dict[str, str], required: list[str], stamped: list[InvoiceLine]) -> str | None:
	"""Every stamped row is a distinct REQUIRED line carrying its frozen item."""
	seen: set[str] = set()
	for line in stamped:
		if line.line_ref not in required:
			return f"existing line {line.line_ref} is not a line this work item posts"
		if line.line_ref in seen:
			return f"existing document carries line {line.line_ref} more than once"
		seen.add(line.line_ref)
		if line.item_code != frozen.get(line.line_ref):
			return f"existing line {line.line_ref} is item {line.item_code!r}, frozen {frozen.get(line.line_ref)!r}"
	return None
