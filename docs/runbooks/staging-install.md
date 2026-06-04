# Runbook: Install the Connector on a Staging ERPNext Site

**Spec**: 001 — Frappe App Foundation | **Implements**: FR-009 | **Date**: 2026-06-04

Canonical staging install guide for `retail_tower_erpnext_connector`. **Staging only** —
production install is gated by [`upgrade-compatibility.md`](./upgrade-compatibility.md)
(constitution Principle III). This is the operational copy of the spec-local
`specs/001-frappe-app-foundation/quickstart.md`.

---

## Prerequisites

- A Frappe **bench** on the supported line: **Frappe v15 / ERPNext v15** (see
  [`../decisions/version-pin-upgrade-policy.md`](../decisions/version-pin-upgrade-policy.md)).
- A **staging** ERPNext site you can install apps onto (never production for this feature).
- Shell access to the bench directory.

> Version compatibility is **declared and documented, not enforced at install time**. A site
> outside the supported v15 line is unsupported; align versions before installing.

## Install steps

From the bench root:

```bash
# 1. Fetch the app into the bench
bench get-app retail_tower_erpnext_connector <repo-url>

# 2. Install onto the staging site
bench --site <staging-site> install-app retail_tower_erpnext_connector

# 3. Run migrations (no-op at the foundation; patches.txt has no patches)
bench --site <staging-site> migrate
```

## Verification

| Check | Command / action | Expected | Maps to |
|-------|------------------|----------|---------|
| App installed | `bench --site <staging-site> list-apps` | lists `retail_tower_erpnext_connector` | US1 / SC-001 |
| Site loads | open the ERPNext desk | loads without error | US1 |
| Metadata clear | inspect the app entry | name, description, publisher, license shown | US1 / FR-002 |
| Settings exist | search "Connector Settings" in the desk | opens the single config record | US2 / SC-002 |
| No business mutation | compare product/stock/sales counts | unchanged from before install | US1 / SC-003 / FR-005 |

## Run the foundation tests (on the bench)

```bash
bench --site <staging-site> run-tests --app retail_tower_erpnext_connector
```

These assert install + metadata, no business mutation, no ERPNext fork, and the Connector
Settings singleton (`tests/test_foundation.py`).

## Uninstall (safety check)

```bash
bench --site <staging-site> uninstall-app retail_tower_erpnext_connector
```

**Expected**: the app and its Connector Settings singleton are removed; ERPNext product,
stock, and sales data are **unchanged** (FR-010 / SC-003) — the app introduced no business
mutations to reverse.

## Validation result (local Docker Frappe v15 dev)

On **2026-06-04**, install / migrate / tests were validated on a local Docker Frappe dev
site (`retail.localhost`, Frappe 15.110.0, ERPNext 15.110.0, connector 0.1.0):

- `install-app` — **PASS**
- `migrate` — **PASS** (no-op)
- `run-tests` — **PASS** (8 tests, OK)
- `list-apps` — connector listed at 0.1.0

**Caveat**: this was local dev validation; Frappe warned MariaDB 11.8 is newer than its
tested range — not a production/staging DB recommendation. The full quickstart end-to-end
(including the uninstall safety check below) is **not yet run**. Full record:
[`specs/001-frappe-app-foundation/bench-validation.md`](../../specs/001-frappe-app-foundation/bench-validation.md).

## Out of scope (later specs)

Data-Pulse-2 authentication (003), product/price export (004), inventory export (005),
sales posting (006), tax/fiscal fields (007), and the full upgrade runbook (008) are not
part of this install. The foundation is structure + documentation only.
