# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Bin-view worker — pure read-and-report logic for one pulled request.

For each :class:`~.transport.BinViewRequest`, the worker reads the live ERPNext ``Bin``
on-hand per Item for the request's warehouse (via an injected :class:`BinReader` — the
frappe-touching part is the bench glue), builds an exact-decimal
:class:`~.contracts.BinViewSnapshotReport`, and reports it back to DP2 with a
deterministic ``Idempotency-Key``.

§III: ERPNext ``Bin.actual_qty`` is a FLOAT; the connector converts it to an
exact-decimal STRING deterministically (round HALF-EVEN to 6 fractional digits — the
019 contract precision cap) so DP2 never receives a float. NO valuation is read.

This module imports NO frappe — the Bin read is behind :class:`BinReader`; tested
locally against a fake. The live composition root is :mod:`.poller` (bench-validated).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Protocol

from .contracts import BinEntry, BinViewRequest, BinViewSnapshotReport
from .transport import BinViewClient, ReportResult

# 019 BinEntry.quantity precision cap — at most 6 fractional digits.
_QTY_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class RawBin:
    """One ERPNext ``Bin`` row as read from the warehouse (item_code + on-hand + uom)."""

    item_code: str
    actual_qty: float
    stock_uom: str


class BinReader(Protocol):
    """Reads the live ERPNext ``Bin`` rows for a warehouse (the frappe-touching seam)."""

    def read_bins(self, *, erpnext_warehouse_ref: str, item_window) -> list[RawBin]: ...


class Clock(Protocol):
    """Supplies the connector ``readAt`` timestamp (ISO-8601 UTC)."""

    def now_iso(self) -> str: ...


def quantize_qty(actual_qty: float) -> str:
    """Convert an ERPNext float ``actual_qty`` to an exact-decimal STRING (§III).

    Round HALF-EVEN to 6 fractional digits (the 019 quantity precision cap). The
    Decimal is built from ``str(actual_qty)`` (not the float directly) so the input's
    decimal repr is honored rather than binary-float drift. Negative is preserved
    (ERPNext may carry negative on-hand).
    """
    d = Decimal(str(actual_qty)).quantize(_QTY_QUANTUM, rounding=ROUND_HALF_EVEN)
    # Normalize "-0.000000" → "0.000000" (sign of zero is not meaningful).
    if d == 0:
        d = abs(d)
    return f"{d:f}"


def build_report(bins: list[RawBin], *, read_at: str) -> BinViewSnapshotReport:
    """Build the snapshot report from raw Bin rows — pure, deterministic, no valuation."""
    entries = tuple(
        BinEntry(
            erpnext_item_ref=b.item_code,
            quantity=quantize_qty(b.actual_qty),
            stock_uom=b.stock_uom,
        )
        for b in bins
    )
    return BinViewSnapshotReport(entries=entries, read_at=read_at)


def derive_idempotency_key(request_ref: str) -> str:
    """Deterministic Idempotency-Key for a request's report.

    Keyed on the ``requestRef`` so a re-report of the SAME request reuses the SAME key
    (DP2 replays idempotently). A different request → a different key.
    """
    return f"binview-{request_ref}"


def process_request(
    request: BinViewRequest,
    *,
    client: BinViewClient,
    reader: BinReader,
    clock: Clock,
) -> ReportResult:
    """Read the warehouse's Bin for one request and report the snapshot to DP2.

    Reads on-hand QUANTITY only (no valuation, 019 / Principle IX). The
    ``Idempotency-Key`` is derived from the requestRef so a retry is a safe replay.
    """
    read_at = clock.now_iso()
    bins = reader.read_bins(
        erpnext_warehouse_ref=request.erpnext_warehouse_ref,
        item_window=request.item_window,
    )
    report = build_report(bins, read_at=read_at)
    return client.report_snapshot(
        request.request_ref,
        report,
        idempotency_key=derive_idempotency_key(request.request_ref),
    )
