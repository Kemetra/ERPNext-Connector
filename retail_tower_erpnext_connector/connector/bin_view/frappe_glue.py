# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Frappe glue for the bin-view worker — BENCH-VALIDATION.

The frappe-touching seam: reads the live ERPNext ``Bin`` rows for a warehouse and
supplies the connector ``readAt`` clock. Imports ``frappe`` (and reads the ``Bin``
doctype), so it is validated on a bench, not locally (standing-rules §6). The pure
quantize/report logic it feeds lives in :mod:`.worker` (unit-tested locally).

Validated ``Bin`` shape (real staging doctype): ``item_code`` (Link Item),
``warehouse`` (Link Warehouse), ``actual_qty`` (Float), ``stock_uom`` (Link UOM).
Reads QUANTITY only — NO valuation/cost field (019 / Principle IX).
"""

from __future__ import annotations

import frappe

from .worker import RawBin


class UtcClock:
    """Connector ``readAt`` clock — ISO-8601 UTC (millisecond precision, trailing 'Z')."""

    def now_iso(self) -> str:
        # frappe.utils.now_datetime is naive-local; use a UTC instant + the contract's
        # date-time shape. get_datetime() round-trips through frappe's tz handling.
        from frappe.utils import now_datetime

        dt = now_datetime()
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class FrappeBinReader:
    """Reads live ERPNext ``Bin`` rows for a warehouse (the 019 on-hand source).

    Reads on-hand QUANTITY only. The ``item_window`` is honored as an opaque scoping
    bound: v1 windows carry null bounds (a single ≤500-item window per warehouse), so
    the reader returns up to ``item_window.max_items`` rows ordered by ``item_code``.
    A future multi-window scheme would translate the opaque ``from_item_ref`` /
    ``to_item_ref`` bounds into an ``item_code`` range filter here.
    """

    def read_bins(self, *, erpnext_warehouse_ref: str, item_window) -> list[RawBin]:
        # Read max_items + 1 so the worker can DETECT a warehouse that exceeds the
        # single v1 window (it raises WindowOverflowError rather than truncate).
        limit = int(getattr(item_window, "max_items", 500)) + 1
        rows = frappe.get_all(
            "Bin",
            filters={"warehouse": erpnext_warehouse_ref},
            fields=["item_code", "actual_qty", "stock_uom"],
            order_by="item_code asc",
            limit=limit,
        )
        return [
            RawBin(
                item_code=str(r["item_code"]),
                actual_qty=float(r["actual_qty"] or 0.0),
                stock_uom=str(r["stock_uom"] or ""),
            )
            for r in rows
        ]
