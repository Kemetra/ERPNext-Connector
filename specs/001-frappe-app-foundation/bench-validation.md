# Spec 001 — Bench Validation Record

**Feature**: 001-frappe-app-foundation | **Date**: 2026-06-04

Record of the v15 bench validation run for the Frappe App Foundation, after PR #3
(implementation) was merged to `main`.

> **Scope of this validation**: local Docker / Frappe dev environment. This is **not** a
> production-grade or certified staging validation. See the caveat below.

---

## Environment

| Component | Value |
|-----------|-------|
| Site | `retail.localhost` |
| Frappe | 15.110.0 (`version-15`) |
| ERPNext | 15.110.0 (`version-15`) |
| Connector | `retail_tower_erpnext_connector` 0.1.0 (`main`) |
| Environment | Local Docker / Frappe dev |

## Commands & Results

| # | Command | Result |
|---|---------|--------|
| 1 | `bench --site retail.localhost install-app retail_tower_erpnext_connector` | **PASS** |
| 2 | `bench --site retail.localhost migrate` | **PASS** |
| 3 | `bench --site retail.localhost run-tests --app retail_tower_erpnext_connector` | **PASS** — Ran 8 tests in 0.046s, OK |
| 4 | `bench --site retail.localhost list-apps` | **PASS** — see below |
| 5 | `bench --site retail.localhost uninstall-app retail_tower_erpnext_connector` (quickstart end-to-end) | **PASS** — app + Connector Settings removed; ERPNext product/stock/sales data unchanged (FR-010, SC-003) |

`list-apps` output:

```
frappe                         15.110.0 version-15
erpnext                        15.110.0 version-15
retail_tower_erpnext_connector 0.1.0 main
```

The 8 passing tests are the foundation assertions in
`retail_tower_erpnext_connector/tests/test_foundation.py`: install + metadata,
no-business-mutation, no-ERPNext-fork, and the Connector Settings singleton.

## Caveat — local environment

During site creation, Frappe warned that **MariaDB 11.8** is newer than the
Frappe-supported/tested range. This is recorded as a **local validation caveat only** — it
does **not** constitute a production or staging database recommendation. A
production/staging validation should run on a Frappe-supported MariaDB version.

## Task outcomes

| Task | Description | Status |
|------|-------------|--------|
| T009 | Install on staging site succeeds; app lists (FR-003, SC-001) | **PASS** (local dev) |
| T010 | `migrate` no-op; desk loads; business data unchanged (FR-010, SC-003) | **PASS** (local dev) |
| T015 | Connector Settings singleton exists/opens; no duplicate (US2) | **PASS** (local dev) |
| T020 | Full foundation test suite passes (`run-tests`) | **PASS** — 8/8 |
| T021 | Quickstart end-to-end incl. **uninstall** (SC-001..SC-005) | **PASS** (local dev) — install → verify → uninstall run; ERPNext business data unchanged after uninstall |

## Conclusion

Spec 001 foundation **install / migrate / tests / full quickstart end-to-end passed on
local Docker Frappe v15 validation**. The app installs cleanly, migrations are a no-op, all
8 foundation tests pass, and the quickstart end-to-end — including the **uninstall** step —
leaves ERPNext product/stock/sales data unchanged on Frappe/ERPNext 15.110.0. All of
T009, T010, T015, T020, and T021 are validated; every SC-001..SC-005 checkpoint passes.

This is **not** a claim of production-grade staging validation — it was run on a local
Docker dev environment with the MariaDB 11.8 caveat noted above. A production/staging
validation should be repeated on a Frappe-supported database substrate.
