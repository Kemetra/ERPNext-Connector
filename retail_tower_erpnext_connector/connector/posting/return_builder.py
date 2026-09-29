# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Partial-return work-item → return Sales Invoice (credit note) builder (RT-16).

A 012 ``reversalKind: return`` (RT-14 D1) carries only the returned lines (``returnLines``, priced by
Backend-Core by the cumulative-difference rule) and how the cash was paid out (``refundTenders``,
RT-14 D3, cash only). It posts a return Sales Invoice that:

  - carries ONLY the returned lines, negated (qty and amount; the rate stays positive), each tagged
	with its ``rt_line_ref`` so the glue links it to the ORIGINAL invoice row by identity (RT-14 D6
	custom field) and takes that row's warehouse;
  - pays the refund out from ``refundTenders`` through the CURRENT tender map (RT-10 D6): it is a new
	cash payout, not a mirror of the sale's tenders, so it applies even to a tender-unknown sale;
  - is unrounded (RT-80) and stock-moving (the glue mirrors the original's ``update_stock``);
  - posts on the return's own business date at its recorded time (RT-63, :func:`reversal_stamp_source`).

It COMPOSES on :func:`builder.build_sales_invoice` — the returned lines become the lines of a
synthetic sale snapshot and the refund tenders its tenders — so money validation (FR-009), the
tender == line total check (amendment 4a) and the payments rows come from the single forward money
path. The result is then negated. Pure: no frappe, no ERPNext call.

Fail closed (all ``validation``): a return with no ``refundTenders`` (the feed INVARIANT says every
return carries them — an outstanding credit note would hide cash that left the drawer), a refund
total that differs from the returned total, an unmapped refund method, and a returned line whose
``lineAmount`` is not exactly ``unitPrice x quantity`` (ERPNext recomputes ``amount = rate x qty``,
so it would post a different amount than Backend-Core recorded).

Tax: like the forward builder, no tax rows are posted (Egyptian VAT is 0 today). A return line with
a non-zero ``taxAmount`` therefore cannot settle and is rejected by the total check.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from decimal import Decimal

from .builder import build_sales_invoice
from .contracts import PostingWorkItem, ReturnLine, SaleLine, SaleTender
from .idempotency import provenance_id
from .posting_time import UTC_CLOCK, PostingStamp, apply_stamp, stamp_for
from .reversal_builder import _negate, reversal_stamp_source


class MissingRefundTenders(Exception):
	"""A ``return`` without ``refundTenders`` (feed INVARIANT breach) — rejected as validation."""

	def __init__(self) -> None:
		super().__init__(
			"return carries no refundTenders — rejected as validation (every return records how the "
			"cash was paid out; posting an outstanding credit note would hide it, RT-10 D6 / RT-14 D3)"
		)


class ReturnPricingMismatch(Exception):
	"""A returned line's ``lineAmount`` is not ``unitPrice x quantity`` exactly — rejected as validation."""

	def __init__(self, line_ref: str, unit_price: str, quantity: str, line_amount: str) -> None:
		super().__init__(
			f"return line {line_ref}: lineAmount {line_amount} != unitPrice {unit_price} x quantity "
			f"{quantity} — ERPNext would post rate x qty instead; rejected as validation"
		)


def build_return_invoice(
	work_item: PostingWorkItem,
	*,
	uom_for: Callable[[str], str],
	warehouse_for: Callable[[str], dict],
	customer_for: Callable[[str], str],
	mode_of_payment_for: Callable[[str], str],
	posting_stamp: PostingStamp | None = None,
) -> dict:
	"""Build the return Sales-Invoice payload for one ``reversalKind: return`` work item.

	Resolvers mirror :func:`builder.build_sales_invoice`; ``mode_of_payment_for`` is the RT-10 D5
	tender map, applied to the refund tenders. ``posting_stamp`` is the glue's site-clock stamp;
	without one the return's own ``recordedAt`` / ``businessDate`` are used in UTC.
	"""
	ref = work_item.reversal_of
	if work_item.kind != "reversal" or ref is None or ref.reversal_kind != "return":
		raise ValueError("build_return_invoice expects a reversal work-item of reversalKind 'return'")
	if not ref.refund_tenders:
		raise MissingRefundTenders()

	returned_sale = dataclasses.replace(
		work_item.sale,
		lines=tuple(_returned_line(work_item, rl) for rl in ref.return_lines),
		tenders=tuple(SaleTender(method=t.method, amount=t.amount) for t in ref.refund_tenders),
	)
	doc = build_sales_invoice(
		dataclasses.replace(work_item, sale=returned_sale),
		uom_for=uom_for,
		warehouse_for=warehouse_for,
		customer_for=customer_for,
		mode_of_payment_for=mode_of_payment_for,
	)

	doc["is_return"] = 1
	doc["update_stock"] = 1  # the glue mirrors the original invoice's update_stock
	for item in doc["items"]:
		item["qty"] = _negate(item["qty"])
		item["amount"] = _negate(item["amount"])
	for payment in doc["payments"]:
		payment["amount"] = _negate(payment["amount"])

	# Provenance is the return's own work item (Connector #28), never the original sale's id.
	doc["rt_source_system"] = work_item.source_system
	doc["rt_external_id"] = provenance_id(work_item)

	stamp = posting_stamp or stamp_for(*reversal_stamp_source(work_item), UTC_CLOCK)
	return apply_stamp(doc, stamp)


def _returned_line(work_item: PostingWorkItem, returned: ReturnLine) -> SaleLine:
	"""The sale line ``returned`` points at, re-quantified to the returned quantity and amount."""
	sale_line = next(line for line in work_item.sale.lines if line.line_ref == returned.line_ref)
	if Decimal(sale_line.unit_price) * Decimal(returned.quantity) != Decimal(returned.line_amount):
		raise ReturnPricingMismatch(
			returned.line_ref, sale_line.unit_price, returned.quantity, returned.line_amount
		)
	return dataclasses.replace(
		sale_line,
		quantity=returned.quantity,
		line_amount=returned.line_amount,
		tax_amount=returned.tax_amount,
	)
