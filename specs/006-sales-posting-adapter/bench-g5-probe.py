# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Re-runnable bench probe for Gate G5 (exactly-once posting dedup) — spec 006.

Run on a staging ERPNext v15 bench where the connector is installed + migrated:

    bench --site <site> console <<'EOF'
    exec(open("specs/006-sales-posting-adapter/bench-g5-probe.py").read())
    EOF

It is NOT a pytest test (frappe's `bench run-tests` aborts on `import pytest` collection across the
app — see the foundation-test caveat in wave-status.md). It is a console probe that re-proves the
G5 behavior validated 2026-06-06, so the two bugs it caught (DuplicateEntryError vs
UniqueValidationError; varchar(140) vs the 012 maxLength 200) have a durable regression guard.

Asserts:
  - the composite UNIQUE index `unique_rt_posting_idem` is present on `tabPosting Log`;
  - `external_id` is varchar(200) (not the default 140) and two ids differing only past char 140 do
    NOT collide into a false duplicate;
  - a duplicate `(source_system, external_id)` is DB-rejected and `record_posted` echoes the
    recorded ref via `IdempotencyConflict` (the corrected `except` catches what frappe v15 raises);
  - re-recording the SAME ref is an idempotent no-op.
It cleans up its own probe rows.
"""

import frappe

from retail_tower_erpnext_connector.connector.posting.contracts import ErpnextDocumentRef
from retail_tower_erpnext_connector.connector.posting.frappe_store import FrappePostingLogStore
from retail_tower_erpnext_connector.connector.posting.idempotency import IdempotencyConflict

_SYS = "g5-probe-sys"
_LONG_A = "X" * 150 + "-AAA"  # differs from _LONG_B only past char 140
_LONG_B = "X" * 150 + "-BBB"


def _cleanup():
    for ext in (_LONG_A, _LONG_B, "G5-0001"):
        frappe.db.delete("Posting Log", {"source_system": _SYS, "external_id": ext})
    frappe.db.commit()


def run():
    store = FrappePostingLogStore()
    _cleanup()
    assert frappe.db.sql(
        "SHOW INDEX FROM `tabPosting Log` WHERE Key_name='unique_rt_posting_idem'"
    ), "G5: composite UNIQUE index missing"

    col = frappe.db.sql("SHOW COLUMNS FROM `tabPosting Log` LIKE 'external_id'", as_dict=True)
    assert "200" in col[0]["Type"], f"G5: external_id must be varchar(200), got {col[0]['Type']}"

    store.record_posted((_SYS, _LONG_A), ErpnextDocumentRef("Sales Invoice", "DOC-A"))
    frappe.db.commit()
    store.record_posted((_SYS, _LONG_B), ErpnextDocumentRef("Sales Invoice", "DOC-B"))
    frappe.db.commit()
    # two long ids differing only past char 140 both recorded -> no truncation collision
    assert store.get_document_ref((_SYS, _LONG_A)).name == "DOC-A"
    assert store.get_document_ref((_SYS, _LONG_B)).name == "DOC-B"

    # re-record same ref -> idempotent no-op
    store.record_posted((_SYS, _LONG_A), ErpnextDocumentRef("Sales Invoice", "DOC-A"))

    # different ref, same key -> IdempotencyConflict (the corrected except path)
    try:
        store.record_posted((_SYS, _LONG_A), ErpnextDocumentRef("Sales Invoice", "DOC-A-DUP"))
        raise AssertionError("G5: duplicate key with different ref was NOT rejected")
    except IdempotencyConflict as exc:
        assert exc.existing.name == "DOC-A"

    frappe.db.rollback()
    _cleanup()
    print("[G5 PROBE] PASS — dedup mechanism holds (unique index, 200-char, conflict echo)")


run()
