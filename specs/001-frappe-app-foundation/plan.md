# Implementation Plan: Frappe App Foundation

**Branch**: `001-frappe-app-foundation` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-frappe-app-foundation/spec.md`

## Summary

Scaffold a single custom Frappe app, `retail_tower_erpnext_connector`, that installs
cleanly on a staging ERPNext site, carries clear metadata, exposes one **Connector
Settings** (Single DocType) placeholder, and ships install + version-pin + staging-upgrade
documentation. The app introduces **no** product, stock, price, or sales mutation and does
**not** fork ERPNext. This is a Wave-2 foundation: structure and documentation only.

## Technical Context

**Language/Version**: Python 3.11+ (as bundled with Frappe v15)

**Primary Dependencies**: Frappe Framework v15, ERPNext v15 (host app; referenced, not
forked), `bench` CLI for app lifecycle

**Storage**: MariaDB (Frappe-managed); this feature defines one Single DocType with no
functional fields — no schema for business data

**Testing**: Frappe test runner (`bench run-tests`); foundation tests assert install
success, presence of the Connector Settings singleton, and absence of business-mutation
DocTypes/hooks

**Target Platform**: ERPNext v15 site on a Frappe bench (staging)

**Project Type**: Single custom Frappe app (single project)

**Performance Goals**: N/A — no runtime operations at the foundation layer

**Constraints**: No business mutation (FR-005); no ERPNext fork or core copying (FR-006);
version compatibility declared/documented, not enforced at install time (spec Assumptions);
additive and upgrade-safe (Constitution III)

**Scale/Scope**: One app, one Single DocType placeholder, three documentation artifacts
(install, version-pin policy, upgrade policy). No data volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial evaluation (pre-design):**

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Data-Pulse-2 is the only orchestration boundary | ✅ Pass | Foundation exposes no inbound operational API; no POS-Pulse/Console path introduced. Single DocType is per-site (per-tenant) by Frappe's site-bounded tenancy. |
| II. No ERPNext fork (connector stays thin) | ✅ Pass | Plan creates a standalone custom app; no ERPNext core copied (FR-006). |
| III. Additive & upgrade-safe changes | ✅ Pass | Only additive artifacts (a new app + one DocType); version pin + staging-upgrade policy documented (FR-007, FR-008). |
| IV. Idempotent mutations | ✅ Pass (N/A) | No mutations exist yet; reinstall must not duplicate the singleton (edge case → covered by Single DocType semantics). |
| V. Observable failures | ✅ Pass (deferred) | No operations to observe at foundation; structured logging/correlation IDs begin at spec 003+. |
| VI. Fiscal & stock truth is never hidden | ✅ Pass (N/A) | No fiscal/stock surfaces at foundation. |
| VII. Spec-driven, contract-first delivery | ✅ Pass | This is spec 001 (the foundation itself), reviewed before any business mutation; FR-005 forbids mutation. |

**Result**: PASS — no violations. Complexity Tracking left empty.

**Post-design re-evaluation (after Phase 1):** See [Post-Design Constitution Re-Check](#post-design-constitution-re-check) below.

## Project Structure

### Documentation (this feature)

```text
specs/001-frappe-app-foundation/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — DocType type decision
├── data-model.md        # Phase 1 output — Connector App + Connector Settings entities
├── quickstart.md        # Phase 1 output — staging install steps (FR-009)
├── spec.md              # Feature specification
└── checklists/
    └── requirements.md  # Spec quality checklist (16/16 pass)
```

*No `contracts/` directory: the foundation exposes no external interface. Data-Pulse-2
authentication and request/response contracts are delivered by spec 003; product/inventory
export surfaces by specs 004–005. Emitting empty contracts here would violate the
proportionality clause of the constitution's governance section.*

### Source Code (repository root)

```text
retail_tower_erpnext_connector/        # the Frappe app package
├── hooks.py                           # app metadata + (empty) hook registrations
├── modules.txt                        # declares the Connector module
├── patches.txt                        # empty at foundation (no migrations)
├── retail_tower_erpnext_connector/
│   └── doctype/
│       └── connector_settings/        # the Single DocType placeholder
│           ├── connector_settings.json
│           └── connector_settings.py  # no business logic
└── tests/
    └── test_foundation.py             # install + singleton + no-mutation assertions

pyproject.toml                         # app packaging metadata + version pin
docs/
├── runbooks/
│   ├── staging-install.md             # FR-009 (mirrors quickstart.md)
│   └── upgrade-compatibility.md       # FR-008
└── decisions/
    └── version-pin-upgrade-policy.md  # FR-007
```

**Structure Decision**: Single custom Frappe app at the repository root, matching the
README's "Suggested Initial Repository Structure". The app package name equals the repo's
owned app name (`retail_tower_erpnext_connector`). Documentation lives under `docs/` per
the README layout; `quickstart.md` in the feature dir is the spec-local copy of the staging
install steps.

## Complexity Tracking

> No Constitution Check violations. No complexity to justify. (Section intentionally empty.)

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 design (data-model.md + quickstart.md, contracts/ skipped):

- **Principle II (no fork)**: Confirmed — `data-model.md` defines only a new Single DocType
  in the connector's own module; nothing references or copies ERPNext core DocTypes.
- **Principle VII (no mutation)**: Confirmed — `connector_settings.py` carries no business
  logic; `hooks.py` registers no document events, scheduled jobs, or overrides that touch
  product/stock/sales. `test_foundation.py` asserts this negatively.
- **Principle III (upgrade-safe)**: Confirmed — `patches.txt` is empty (no migrations);
  version pin recorded in `pyproject.toml` and `docs/decisions/version-pin-upgrade-policy.md`.
- **Principle I (tenancy)**: Confirmed — Single DocType is site-scoped; no cross-site data.

**Result**: PASS (post-design). No new violations introduced by the design. Ready for
`/speckit-tasks`.
