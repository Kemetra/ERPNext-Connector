# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Frozen read-models for the fixed 019 stock-view (Bin) contract.

These mirror Data-Pulse-2's ``stock-view.yaml`` (1.0.0-draft) 1:1. The contract is
DP2-owned and read-only (Principle I/IV) — these DTOs CITE it, never re-derive it.

Wire shapes consumed/produced here:
  - ``BinViewRequest`` (pulled): one wanted Bin read for a store's mapped warehouse,
    correlated to a 017 run, scoped to a ≤500-item window;
  - ``BinEntry`` (produced): one ERPNext Item's on-hand QUANTITY (exact-decimal
    string, NEVER a float — Principle III) + its ``stockUom``; NO valuation;
  - ``BinViewSnapshotReport`` (produced): the per-item snapshot + the connector
    ``readAt`` clock.

This module imports NO frappe — pure-Python core, unit-tested locally.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class BinViewItemWindow:
    """019 ``BinViewItemWindow`` — the ≤500-item slice this request covers.

    The connector treats the bounds as opaque scoping; it reports the Bin items that
    fall in the window, up to ``max_items``.
    """

    window_seq: int
    max_items: int
    from_item_ref: str | None
    to_item_ref: str | None

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> BinViewItemWindow:
        return cls(
            window_seq=int(wire["windowSeq"]),  # type: ignore[arg-type]
            max_items=int(wire["maxItems"]),  # type: ignore[arg-type]
            from_item_ref=(None if wire.get("fromItemRef") is None else str(wire["fromItemRef"])),
            to_item_ref=(None if wire.get("toItemRef") is None else str(wire["toItemRef"])),
        )


@dataclass(frozen=True)
class BinViewRequest:
    """019 ``BinViewRequest`` — one wanted ERPNext-Bin read (DP2 → connector)."""

    request_ref: str
    store_id: str
    erpnext_warehouse_ref: str
    run_ref: str
    item_window: BinViewItemWindow
    item_cursor: str

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> BinViewRequest:
        return cls(
            request_ref=str(wire["requestRef"]),
            store_id=str(wire["storeId"]),
            erpnext_warehouse_ref=str(wire["erpnextWarehouseRef"]),
            run_ref=str(wire["runRef"]),
            item_window=BinViewItemWindow.from_wire(wire["itemWindow"]),  # type: ignore[arg-type]
            item_cursor=str(wire["itemCursor"]),
        )


@dataclass(frozen=True)
class BinEntry:
    """019 ``BinEntry`` — one Item's on-hand quantity, exact-decimal string, NO valuation."""

    erpnext_item_ref: str
    quantity: str
    stock_uom: str

    def to_wire(self) -> dict[str, object]:
        return {
            "erpnextItemRef": {"doctype": "Item", "name": self.erpnext_item_ref},
            "quantity": self.quantity,
            "stockUom": self.stock_uom,
        }


@dataclass(frozen=True)
class BinViewSnapshotReport:
    """019 ``BinViewSnapshotReport`` — the connector's point-in-time Bin snapshot."""

    entries: tuple[BinEntry, ...]
    read_at: str

    def to_wire(self) -> dict[str, object]:
        return {
            "entries": [e.to_wire() for e in self.entries],
            "readAt": self.read_at,
        }
