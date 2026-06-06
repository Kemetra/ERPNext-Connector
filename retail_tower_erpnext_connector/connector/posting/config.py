# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Pure Connector Settings parsers (frappe-free).

The poller's ``_load_*`` stubs read Connector Settings child tables (a frappe-coupled, bench-only
act via ``frappe.get_doc``) and then transform the raw DocType rows into the dict shapes
:class:`uom.UomMap` / :class:`uom.PreResolvedWarehouse` / :class:`uom.StoreCustomerMap` consume.

That TRANSFORM is split out here as pure functions so the branching logic (empty rows, blank
values, duplicate keys) is unit-testable WITHOUT frappe — leaving only a three-line frappe read in
the poller shell. Each row is a plain mapping (a Frappe child-table row exposes ``.get(field)`` and
is dict-like) or a Document with field attributes; we read by field name either way.

Fail-loud philosophy (Principle VI): a half-filled or duplicate config row is a CONFIG error
surfaced at load time, never a silent skip — a silently-dropped mapping would later masquerade as a
data problem (an "unmapped unit/store" rejection on a sale that was actually mis-configured).

This module imports NO frappe.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


class ConfigError(Exception):
    """A Connector Settings row is malformed (blank field or duplicate key) — fail loud."""


def _row_get(row: object, field: str) -> str:
    """Read ``field`` from a child-table row (dict-like or attr-like), as a stripped string."""
    if isinstance(row, Mapping):
        value = row.get(field)
    else:  # a Frappe Document row exposes fields as attributes
        value = getattr(row, field, None)
    return "" if value is None else str(value).strip()


def _parse_pairs(
    rows: Iterable | None, key_field: str, value_field: str, label: str
) -> dict[str, str]:
    """Parse child rows into a ``{key: value}`` dict; raise on a blank field or duplicate key."""
    out: dict[str, str] = {}
    for row in rows or []:
        key = _row_get(row, key_field)
        value = _row_get(row, value_field)
        if not key or not value:
            raise ConfigError(
                f"{label} row is incomplete: {key_field}={key!r}, {value_field}={value!r} "
                "(both are required — fix the Connector Settings row, do not leave it half-filled)"
            )
        if key in out:
            raise ConfigError(
                f"{label} has a duplicate {key_field}={key!r} — ambiguous mapping "
                "(remove the duplicate row; the connector never silently picks last-wins)"
            )
        out[key] = value
    return out


def parse_uom_map(rows: Iterable | None) -> dict[str, str]:
    """Child rows ``{dp2_unit, erpnext_uom}`` → ``{unit: uom}`` for :class:`uom.UomMap`."""
    return _parse_pairs(rows, "dp2_unit", "erpnext_uom", "UOM map")


def parse_warehouse_map(rows: Iterable | None) -> dict[str, dict]:
    """Child rows ``{store_id, warehouse}`` → ``{store_id: {doctype, name}}`` for the applier.

    Addresses the warehouse generically as ``{doctype:"Warehouse", name}`` (Principle II, FR-002).
    """
    pairs = _parse_pairs(rows, "store_id", "warehouse", "warehouse map")
    return {store: {"doctype": "Warehouse", "name": name} for store, name in pairs.items()}


def parse_store_customer_map(rows: Iterable | None) -> dict[str, str]:
    """Child rows ``{store_id, customer}`` → ``{store_id: customer}`` for the customer map (F-009)."""
    return _parse_pairs(rows, "store_id", "customer", "store→customer map")
