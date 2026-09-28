# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Work-item → ERPNext Sales-Invoice payload builder (T030/T033/T034).

A pure dict-transform: given a :class:`PostingWorkItem`, produce the ERPNext Sales-Invoice
document payload the connector will submit. It:

  - **applies** each line's pre-resolved ``erpnextItemRef`` as the ``item_code`` — there is
    deliberately NO item-resolution hook (rider R2 / FR-001); the only injected callables are
    a UOM resolver (FR-008) and a warehouse resolver (FR-010, applying the DP2-pre-resolved id);
  - keeps every monetary value an **exact-decimal string** (never float — FR-009);
  - carries ``businessDate`` → ``posting_date`` (never the connector's post-time — T033) with
    ``set_posting_time = 1`` so ERPNext keeps it, and ``posting_time`` from ``occurredAt``
    (RT-49 rule, ``posting_time.stamp_for``; ERPNext would otherwise overwrite both with "now");
  - addresses everything generically (``item_code`` / ``Warehouse`` name — FR-002, Principle II);
  - posts with ``update_stock=1`` (RT-48, owner decision RT-47 D1): the Sales Invoice IS the
    stock-moving document. ERPNext writes the Stock Ledger Entries inside the SAME submit, so the
    existing SI idempotency (Posting Log + ``unique_rt_si_provenance``) is also the stock
    exactly-once guarantee. No Delivery Note.

This module imports NO frappe — it builds a plain dict the bench glue submits. The interim
mode posts a submitted Sales Invoice only (outstanding AR; rider R1) — no Payment Entry here.
"""

from __future__ import annotations

from collections.abc import Callable

from .contracts import PostingWorkItem
from .posting_time import UTC_CLOCK, PostingStamp, apply_stamp, stamp_for


class UnmappedUnit(Exception):
    """A DP2 free-text ``unit`` has no entry in the signed unit→UOM map (FR-008).

    The caller maps this to a ``permanently_rejected`` / ``validation`` outcome — never a
    silent default (Principle VI). Raised by the injected UOM resolver.
    """

    def __init__(self, unit: str) -> None:
        super().__init__(f"unit {unit!r} has no ERPNext UOM mapping (fail-closed → validation)")
        self.unit = unit


def build_sales_invoice(
    work_item: PostingWorkItem,
    *,
    uom_for: Callable[[str], str],
    warehouse_for: Callable[[str], dict],
    customer_for: Callable[[str], str],
    posting_stamp: PostingStamp | None = None,
) -> dict:
    """Build the ERPNext Sales-Invoice payload for one ``sale_post`` work-item.

    ``uom_for(unit) -> erpnext_uom`` resolves the signed unit→UOM map (raises
    :class:`UnmappedUnit` on a miss). ``warehouse_for(store_id) -> {doctype, name}`` returns
    the DP2-pre-resolved warehouse identity (rider R5; never guessed by this builder).
    ``customer_for(store_id) -> customer`` resolves the operator-configured store→Customer map
    (F-009; raises :class:`uom.UnmappedStore` on a miss — the builder NEVER fabricates a
    customer, which would hide a config gap; Principle VI).
    ``posting_stamp`` is the RT-49 posting date/time; the glue computes it with the ERPNext site
    clock. Without one, it is derived from ``occurredAt`` in UTC (``posting_time.UTC_CLOCK``).
    """
    sale = work_item.sale
    warehouse = warehouse_for(sale.store_id)
    # F-009: the 012 work-item carries no customer identity — only Sale.store_id. The operator
    # maps each store to its ERPNext Customer (config, injected) exactly as for the warehouse.
    customer = customer_for(sale.store_id)

    items = []
    for line in sale.lines:
        items.append(
            {
                # Apply the pre-resolved Item identity — no lookup (rider R2).
                "item_code": line.erpnext_item_ref.name,
                "qty": line.quantity,
                "uom": uom_for(line.unit),
                "rate": line.unit_price,
                "amount": line.line_amount,
                "warehouse": warehouse["name"],
                "currency": line.currency_code,
            }
        )

    # F-009 CLOSED: the customer is resolved from the operator-configured store→Customer map
    # (above), never fabricated. The 012 work-item carries no customer; the operator owns the
    # mapping, identical to the UOM and warehouse maps. `company` is left to ERPNext's default
    # company (single-company sites); a multi-company store→company mapping is a future extension
    # if needed — but the customer is the field that actually blocks submit on a configured bench.
    doc = {
        "doctype": "Sales Invoice",
        "customer": customer,
        "currency": sale.currency_code,
        # Provenance for idempotency + audit (O-3); carried on custom fields.
        "rt_source_system": sale.source_system,
        "rt_external_id": sale.external_id,
        "rt_sale_ref": sale.sale_ref,
        # RT-48 / RT-47 D1: the sale moves stock out of each line's mapped store warehouse.
        "update_stock": 1,
        "items": items,
    }

    # FR-009 enforced in the path (not only by a separately-callable check): every monetary
    # field is an exact-decimal string + ISO-4217, never a float. Local import avoids the
    # builder↔uom import cycle (uom imports UnmappedUnit from this module).
    from .uom import assert_money_conformance

    assert_money_conformance(doc)
    # businessDate drives the fiscal period — never the connector's post-time (T033). RT-49:
    # set_posting_time=1, or ERPNext overwrites posting_date/posting_time with "now".
    stamp = posting_stamp or stamp_for(sale.occurred_at, sale.business_date, UTC_CLOCK)
    return apply_stamp(doc, stamp)
