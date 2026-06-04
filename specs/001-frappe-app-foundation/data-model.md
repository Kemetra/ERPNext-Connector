# Phase 1 Data Model: Frappe App Foundation

**Feature**: 001-frappe-app-foundation | **Date**: 2026-06-04

The foundation introduces **no business data**. It defines one configuration singleton and
the app package metadata. Per Constitution Principle VII (FR-005), no product, stock, price,
or sales entity is created.

---

## Entity: Connector App (packaging metadata, not a DocType)

The installable unit and its identifying metadata. Not stored as a DocType — it is the
Frappe app package itself, described in `hooks.py` / `pyproject.toml`.

| Attribute | Value / Source | Requirement |
|-----------|----------------|-------------|
| App name | `retail_tower_erpnext_connector` | FR-001 |
| Title / description | "Retail Tower ERPNext Connector" + purpose line | FR-002 |
| Publisher | Retail Tower OS | FR-002 |
| License | Per repository LICENSE | FR-002 |
| App version | SemVer in `pyproject.toml`, starting `0.1.0` | FR-007 |
| Required apps | `frappe`, `erpnext` (v15 line) | FR-007 |

---

## Entity: Connector Settings (Single DocType)

A site-wide singleton acting as the future anchor for integration configuration. At the
foundation it is an **empty placeholder** — present and openable, with no active behavior.

| Property | Value |
|----------|-------|
| DocType name | `Connector Settings` |
| Type | **Single** (site-wide singleton) |
| Module | Connector (declared in `modules.txt`) |
| Functional fields | **None** at foundation. At most a non-functional marker/note field describing it as a placeholder. |
| Permissions | System Manager read/write (default admin scope); no public exposure |
| Business logic | None — `connector_settings.py` defines the controller class with no overrides |

**Identity & uniqueness**: Single DocType → exactly one record per site, enforced by the
framework. No custom uniqueness logic.

**Lifecycle / state transitions**:
- **Install**: the singleton becomes available (Frappe creates the Single record on demand).
- **Reinstall / double-install**: no duplicate record (Single semantics) — satisfies the
  reinstall edge case and Principle IV intent.
- **Uninstall**: the DocType and its singleton are removed; **no ERPNext business data is
  touched** (FR-010, SC-003), because the app introduced none.

**Validation rules**: None required at foundation (no functional fields). Future fields and
their validation are added by later specs (003+) against their own contracts.

---

## Explicitly absent (by design — Constitution Principle VII / FR-005)

- No Item / Product, Stock / Bin, Price List, or Sales/POS Invoice DocTypes or extensions.
- No document-event hooks, scheduled jobs, or overrides touching ERPNext business data.
- No migrations (`patches.txt` empty) — nothing to migrate at the scaffold layer.

`test_foundation.py` asserts these negatives (the app declares no DocType that writes
business data and registers no such hooks).
