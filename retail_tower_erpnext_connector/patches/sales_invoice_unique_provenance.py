# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Add a composite UNIQUE index on Sales Invoice (rt_source_system, rt_external_id).

This closes Gate G5 / F-002 (the crash-between-submit-and-record window): the Posting Log unique
index makes the connector's OWN dedup exactly-once, but a crash AFTER ``sinv.submit()`` and BEFORE
``record_posted()`` leaves no Posting Log row — so a DP2 re-offer's replay guard finds nothing and
submits a SECOND Sales Invoice. A UNIQUE index on the SI's provenance columns makes that second
submit fail at the database, which ``frappe_glue.post_work_item`` catches and resolves to the
already-posted SI (echo its documentRef) instead of creating a duplicate.

The columns are the ``rt_source_system`` / ``rt_external_id`` provenance Custom Fields (declared in
``fixtures/custom_field.json``, synced before this patch). MariaDB allows MULTIPLE NULLs in a unique
index, so manual / non-connector Sales Invoices (which carry NULL provenance) are unaffected — only
connector-posted SIs (both columns non-NULL) are deduped.

Idempotent + reversible:
  - rollback note: DROP INDEX unique_rt_si_provenance ON the "tabSales Invoice" table (additive
    index; safe to drop — no data loss, reverts to non-unique behaviour).
"""

import frappe

_INDEX = "unique_rt_si_provenance"
_TABLE = "tabSales Invoice"


def execute() -> None:
    if not frappe.db.table_exists("Sales Invoice"):
        return  # defensive — erpnext should have created it
    # The provenance Custom Fields must be synced (their columns must exist) before indexing them.
    cols = {c["Field"] for c in frappe.db.sql(f"SHOW COLUMNS FROM `{_TABLE}`", as_dict=True)}
    if "rt_source_system" not in cols or "rt_external_id" not in cols:
        # Custom Fields not yet synced — skip; a later migrate (after fixtures sync) re-runs this.
        return
    existing = frappe.db.sql(f"SHOW INDEX FROM `{_TABLE}` WHERE Key_name = %s", (_INDEX,))
    if existing:
        return  # already applied — idempotent re-run
    frappe.db.sql(
        f"ALTER TABLE `{_TABLE}` "
        f"ADD UNIQUE INDEX `{_INDEX}` (`rt_source_system`, `rt_external_id`)"
    )
