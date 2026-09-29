# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-78 — the pure tender → ERPNext Mode of Payment resolver (RT-10 D5, fail closed)."""

import pytest

from retail_tower_erpnext_connector.connector.posting import tender as t


class TestTenderModeMap:
    def test_resolves_a_mapped_method(self):
        assert t.TenderModeMap({"cash": "Cash"}).resolve("cash") == "Cash"

    def test_unmapped_method_fails_closed(self):
        # No default Mode of Payment, ever (D5): the item is rejected as validation.
        with pytest.raises(t.UnmappedTender, match="card_external"):
            t.TenderModeMap({"cash": "Cash"}).resolve("card_external")

    def test_empty_map_fails_closed(self):
        with pytest.raises(t.UnmappedTender):
            t.TenderModeMap({}).resolve("cash")
