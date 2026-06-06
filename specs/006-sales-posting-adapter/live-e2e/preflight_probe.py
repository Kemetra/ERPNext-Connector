# Preflight probe (bench-only, throwaway) — confirm the F-009 acceptance run can submit.
#
# Checks: (1) a default Company is set (Global Defaults) — the builder dropped `company`, betting
# the default; if absent, submit fails and we need a store_company_map. (2) The masters the
# posted-path session created still exist (Company/Customer/Item/Warehouse/UOM). Prints a report.
#
# Copy into the bench app dir then: bench --site retail.localhost execute
#   retail_tower_erpnext_connector.connector.posting.preflight_probe.main

import frappe


def main():
    print("=== F-009 preflight ===")
    default_company = frappe.defaults.get_global_default("company")
    print("DEFAULT_COMPANY=%r" % default_company)
    companies = frappe.get_all("Company", pluck="name")
    print("COMPANIES=%r" % companies)
    # The masters the posted-path session seeded (names from wave-status: E2E Co / E2E Customer /
    # TEST-ITEM-01 / Stores - E2E / Nos).
    for dt, name in (
        ("Customer", "E2E Customer"),
        ("Item", "TEST-ITEM-01"),
        ("Warehouse", "Stores - E2E"),
        ("UOM", "Nos"),
    ):
        exists = frappe.db.exists(dt, name)
        print("%s %r exists=%s" % (dt, name, bool(exists)))
    # Any warehouse under the default company (the harness used 'Stores - E2E').
    whs = frappe.get_all("Warehouse", pluck="name")
    print("WAREHOUSES=%r" % whs[:10])
    custs = frappe.get_all("Customer", pluck="name")
    print("CUSTOMERS=%r" % custs[:10])
