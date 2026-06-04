# Decision: Version Pin & Upgrade Policy

**Spec**: 001 — Frappe App Foundation | **Status**: Accepted | **Date**: 2026-06-04

Implements FR-007 (supported version range) and supports FR-008 (upgrade policy).
Anchored to constitution Principle III (additive & upgrade-safe changes).

---

## Supported version range

| Component | Supported line | Notes |
|-----------|----------------|-------|
| Frappe Framework | **v15** | Host framework |
| ERPNext | **v15** | ERP/accounting/inventory backend; declared as `required_apps` in `hooks.py` |
| Python | **>= 3.10** | As pinned in `pyproject.toml` (`requires-python`) |

The connector is developed and validated against the **v15** major line of both Frappe and
ERPNext. The app's own version starts at **`0.1.0`** (`retail_tower_erpnext_connector/__init__.py`).

## Enforcement stance — declared, not blocked

Version compatibility is **declared and documented, not enforced as install-blocking logic**
(research.md Decision 2). The foundation adds no `before_install` version gate.

- `required_apps = ["erpnext"]` ensures the app cannot install on a site **without** ERPNext,
  but does not pin a specific ERPNext *version*.
- If a site runs an ERPNext/Frappe version outside the v15 line, that configuration is
  **unsupported**. The expected operator action is to align the site to the supported v15
  line (or wait for a connector release that supports the target line) before installing or
  upgrading. `bench` will surface gross incompatibilities during install/migrate.

## Revising the pin

The supported range is revised only through this document plus a corresponding bump to the
app version and `pyproject.toml`, validated via the upgrade workflow in
[`../runbooks/upgrade-compatibility.md`](../runbooks/upgrade-compatibility.md). Production
upgrades follow the staging-first sequence defined there — never applied directly in
production (constitution Principle III).
