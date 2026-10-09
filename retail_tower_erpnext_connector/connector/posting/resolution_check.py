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
  multiset (equal for a ``sale_post``, contained for a ``reversal``).

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
	frozen = work_item.sale.warehouse_ref
	if frozen is None:
		return None
	for line in invoice.items:
		if line.warehouse != frozen["name"]:
			return f"existing line warehouse {line.warehouse!r} is not the frozen {frozen['name']!r}"
	return None


def _item_mismatch(work_item: PostingWorkItem, invoice: InvoiceSnapshot) -> str | None:
	frozen = {line.line_ref: line.erpnext_item_ref.name for line in work_item.sale.lines if line.line_ref}
	stamped = [line for line in invoice.items if line.line_ref is not None]
	if stamped and len(stamped) == len(invoice.items):
		return _by_line_ref(work_item.kind, frozen, stamped)
	expected = Counter(line.erpnext_item_ref.name for line in work_item.sale.lines)
	actual = Counter(line.item_code for line in invoice.items)
	covered = actual == expected if work_item.kind == "sale_post" else not (actual - expected)
	return (
		None
		if covered
		else f"existing item codes {sorted(actual)} do not match the frozen {sorted(expected)}"
	)


def _by_line_ref(kind: str, frozen: dict[str, str], stamped: list[InvoiceLine]) -> str | None:
	for line in stamped:
		expected = frozen.get(line.line_ref)
		if expected is None:
			return f"existing line {line.line_ref} is not a frozen sale line"
		if line.item_code != expected:
			return f"existing line {line.line_ref} is item {line.item_code!r}, frozen {expected!r}"
	if kind == "sale_post" and {line.line_ref for line in stamped} != set(frozen):
		return "existing document does not carry every frozen sale line"
	return None
