# Quickstart: Install the Connector on a Staging ERPNext Site

**Feature**: 001-frappe-app-foundation | **Date**: 2026-06-04

This is the spec-local staging install guide (FR-009 / US3). The canonical copy lives at
`docs/runbooks/staging-install.md`. **Staging only** — production install is out of scope
and gated by the upgrade policy (FR-008).

---

## Prerequisites

- A Frappe **bench** running the supported version line: **Frappe v15 / ERPNext v15**
  (see `docs/decisions/version-pin-upgrade-policy.md` for the exact pin).
- A **staging** ERPNext site you can install apps onto (never production for this feature).
- Shell access to the bench directory.

> Version compatibility is **declared and documented, not enforced at install time**. If
> your site is outside the supported range, `bench` may still attempt the install; the
> version-pin policy states this configuration is unsupported and to align versions first.

---

## Install steps

1. **Fetch the app into the bench** (from the bench root):

   ```bash
   bench get-app retail_tower_erpnext_connector <repo-url>
   ```

2. **Install the app onto the staging site**:

   ```bash
   bench --site <staging-site> install-app retail_tower_erpnext_connector
   ```

3. **Run migrations** (no-op at the foundation; `patches.txt` is empty):

   ```bash
   bench --site <staging-site> migrate
   ```

---

## Verification (maps to acceptance scenarios)

| Check | Expected result | Scenario |
|-------|-----------------|----------|
| App is installed | `bench --site <staging-site> list-apps` shows `retail_tower_erpnext_connector` | US1 / SC-001 |
| Site loads normally | The ERPNext desk opens without error | US1 |
| Metadata is clear | App entry shows the connector name, description, publisher, license | US1 / FR-002 |
| Connector Settings exists | Searching "Connector Settings" in the desk opens the single config record | US2 / SC-002 |
| No business mutation | Product / stock / sales counts are unchanged from before install | US1 / SC-003 / FR-005 |

---

## Uninstall (safety check)

```bash
bench --site <staging-site> uninstall-app retail_tower_erpnext_connector
```

**Expected**: the app and its Connector Settings singleton are removed; ERPNext product,
stock, and sales data are **unchanged** (FR-010 / SC-003) — the app introduced no business
mutations to reverse.

---

## Out of scope (later specs)

Authentication to Data-Pulse-2 (003), product/price export (004), inventory export (005),
sales posting (006), tax/fiscal fields (007), and the full upgrade runbook (008) are **not**
part of this install. The foundation is structure + documentation only.
