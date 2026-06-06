# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Local unit tests for the pure Connector Settings config parsers.

The poller's `_load_*` stubs read Connector Settings (a frappe-coupled, bench-only act) and then
transform the raw DocType rows into the dict shapes UomMap / PreResolvedWarehouse / StoreCustomerMap
consume. That TRANSFORM is split out as pure functions in `config.py` so it is unit-testable here
WITHOUT frappe — the only bench-only part left is the three-line `frappe.get_doc` read.

This pays down the connector's test-infra debt for THIS slice's own code: the parsing logic (the
part with real branching: empty rows, blank values, duplicate keys) is covered locally; only the
frappe read shell is bench-probe-guarded.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import config as cfg


class TestParseUomMap:
    def test_parses_child_rows_to_unit_uom_dict(self):
        rows = [
            {"dp2_unit": "each", "erpnext_uom": "Nos"},
            {"dp2_unit": "kg", "erpnext_uom": "Kg"},
        ]
        assert cfg.parse_uom_map(rows) == {"each": "Nos", "kg": "Kg"}

    def test_empty_rows_yield_empty_map(self):
        # An unconfigured map is a clean empty dict — the UomMap then fails closed per-unit
        # (not a crash here). None (single-doctype unset child table) is treated as empty.
        assert cfg.parse_uom_map([]) == {}
        assert cfg.parse_uom_map(None) == {}

    def test_blank_or_partial_row_is_rejected(self):
        # A half-filled row (a unit with no UOM, or vice versa) is a config error, not a silent
        # skip — surfacing it beats a mapping that silently lacks an entry (Principle VI).
        with pytest.raises(cfg.ConfigError):
            cfg.parse_uom_map([{"dp2_unit": "each", "erpnext_uom": ""}])
        with pytest.raises(cfg.ConfigError):
            cfg.parse_uom_map([{"dp2_unit": "", "erpnext_uom": "Nos"}])

    def test_duplicate_unit_is_rejected(self):
        # Two rows mapping the same unit to different UOMs is ambiguous — fail loud, never let the
        # last-wins silently pick one (a posting would depend on row order).
        with pytest.raises(cfg.ConfigError):
            cfg.parse_uom_map(
                [
                    {"dp2_unit": "each", "erpnext_uom": "Nos"},
                    {"dp2_unit": "each", "erpnext_uom": "Unit"},
                ]
            )


class TestParseWarehouseMap:
    def test_parses_rows_to_store_warehouse_identity(self):
        rows = [{"store_id": "s1", "warehouse": "Stores - E2E"}]
        assert cfg.parse_warehouse_map(rows) == {
            "s1": {"doctype": "Warehouse", "name": "Stores - E2E"}
        }

    def test_empty_rows_yield_empty_map(self):
        assert cfg.parse_warehouse_map([]) == {}
        assert cfg.parse_warehouse_map(None) == {}

    def test_blank_row_is_rejected(self):
        with pytest.raises(cfg.ConfigError):
            cfg.parse_warehouse_map([{"store_id": "s1", "warehouse": ""}])

    def test_duplicate_store_is_rejected(self):
        with pytest.raises(cfg.ConfigError):
            cfg.parse_warehouse_map(
                [
                    {"store_id": "s1", "warehouse": "WH-A"},
                    {"store_id": "s1", "warehouse": "WH-B"},
                ]
            )


class TestRequireConfiguredMaps:
    # Codex PR #23 P1: a half-configured connector (creds saved, a required map still empty) must
    # SKIP the tick (run_posting_poll catches the raise → posting.poll.skipped, sales stay pending),
    # NOT activate and mass-reject every pending sale as terminal validation. Every work-item has a
    # store + >=1 line, so an empty uom/warehouse/customer map => 100% rejection — indistinguishable
    # from "not yet configured". So an EMPTY required map raises ConfigError (→ skip).
    def test_all_maps_populated_passes(self):
        cfg.require_configured_maps(
            uom={"each": "Nos"},
            warehouse={"s1": {"doctype": "Warehouse", "name": "WH"}},
            customer={"s1": "C1"},
        )  # must not raise

    def test_empty_uom_map_raises(self):
        with pytest.raises(cfg.ConfigError):
            cfg.require_configured_maps(uom={}, warehouse={"s1": {}}, customer={"s1": "C1"})

    def test_empty_warehouse_map_raises(self):
        with pytest.raises(cfg.ConfigError):
            cfg.require_configured_maps(uom={"each": "Nos"}, warehouse={}, customer={"s1": "C1"})

    def test_empty_customer_map_raises(self):
        with pytest.raises(cfg.ConfigError):
            cfg.require_configured_maps(
                uom={"each": "Nos"}, warehouse={"s1": {}}, customer={}
            )

    def test_error_names_every_empty_map(self):
        # The skip-reason log should say WHICH maps are unconfigured, not just "a map is empty".
        with pytest.raises(cfg.ConfigError) as exc:
            cfg.require_configured_maps(uom={}, warehouse={}, customer={"s1": "C1"})
        msg = str(exc.value)
        assert "uom" in msg.lower() and "warehouse" in msg.lower()

    def test_does_not_swallow_partial_miss(self):
        # REGRESSION GUARD against over-correcting: a NON-empty map with a specific key absent is a
        # genuine terminal rejection (decision-table rows 5/8), NOT a skip. require_configured_maps
        # only gates the EMPTY (not-configured) state — it must not inspect individual keys, so a
        # populated-but-incomplete map passes the gate (the per-item UnmappedUnit/UnmappedStore
        # reject still fires downstream in frappe_glue, unchanged).
        cfg.require_configured_maps(
            uom={"each": "Nos"},  # "kg" absent — store B unmapped — still must NOT skip
            warehouse={"s1": {"doctype": "Warehouse", "name": "WH"}},
            customer={"s1": "C1"},
        )  # must not raise — partial config is "live", not "unconfigured"


class TestParseStoreCustomerMap:
    def test_parses_rows_to_store_customer_dict(self):
        rows = [{"store_id": "s1", "customer": "Walk-in Customer - RT"}]
        assert cfg.parse_store_customer_map(rows) == {"s1": "Walk-in Customer - RT"}

    def test_empty_rows_yield_empty_map(self):
        assert cfg.parse_store_customer_map([]) == {}
        assert cfg.parse_store_customer_map(None) == {}

    def test_blank_row_is_rejected(self):
        with pytest.raises(cfg.ConfigError):
            cfg.parse_store_customer_map([{"store_id": "s1", "customer": ""}])

    def test_duplicate_store_is_rejected(self):
        with pytest.raises(cfg.ConfigError):
            cfg.parse_store_customer_map(
                [
                    {"store_id": "s1", "customer": "C-A"},
                    {"store_id": "s1", "customer": "C-B"},
                ]
            )
