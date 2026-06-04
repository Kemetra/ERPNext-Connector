---
description: "Task list for Frappe App Foundation implementation"
---

# Tasks: Frappe App Foundation

**Input**: Design documents from `/specs/001-frappe-app-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included. The constitutional no-mutation guarantee (FR-005) and the singleton
guarantee (FR-004) are only verifiable by tests; the plan names `test_foundation.py`
explicitly. Tests here are the enforcement mechanism for these requirements, not a generic
TDD overlay.

**Organization**: Tasks grouped by user story (US1 install, US2 Connector Settings, US3
docs) so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task serves (US1, US2, US3)
- All paths are relative to the repository root

## Path Conventions

Single custom Frappe app at the repository root. App package:
`retail_tower_erpnext_connector/`. Docs under `docs/`. Per plan.md "Structure Decision".

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the Frappe app package skeleton that everything else attaches to.

- [X] T001 Create app package directory structure per plan.md: `retail_tower_erpnext_connector/` with nested `retail_tower_erpnext_connector/connector/doctype/`, and a top-level `tests/` and `docs/` (`docs/runbooks/`, `docs/decisions/`)
- [X] T002 Create `pyproject.toml` at repo root with app packaging metadata, version dynamic from `__init__.py` (`0.1.0`), flit build backend per FR-007 and research.md Decision 2
- [X] T003 [P] Create `retail_tower_erpnext_connector/modules.txt` declaring the `Connector` module
- [X] T004 [P] Create empty `retail_tower_erpnext_connector/patches.txt` (section headers only; no migrations at foundation, per data-model.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: App metadata and module wiring that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `retail_tower_erpnext_connector/hooks.py` with app metadata (`app_name`, `app_title` "Retail Tower ERPNext Connector", `app_publisher` "Retail Tower OS", `app_description`, `app_email`, `app_license`) per FR-002; `required_apps = ["erpnext"]`; register NO document-event hooks, scheduled jobs, or overrides (FR-005)
- [X] T006 [P] Create `retail_tower_erpnext_connector/__init__.py` exposing `__version__ = "0.1.0"` (flit reads it via `dynamic`)

**Checkpoint**: App package is metadata-complete and installable as an empty app — user story implementation can now begin.

---

## Phase 3: User Story 1 - Install on staging ERPNext site (Priority: P1) 🎯 MVP

**Goal**: The app installs cleanly on a staging ERPNext site, loads without error, shows clear metadata, and changes no ERPNext business data.

**Independent Test**: On a fresh staging site, `bench install-app retail_tower_erpnext_connector` succeeds, the app appears in `list-apps`, the desk loads, and product/stock/sales counts are unchanged.

### Tests for User Story 1 ⚠️

> **Bench-dependent validation** (not locally-runnable red-green TDD): these tests assert
> against a *live installed app* (installed-apps list, DocType registration), so they
> execute on a staging ERPNext bench, not in this repo. Author them before T009/T010;
> run them on the bench during T020.

- [X] T007 [US1] Write install + metadata test in `retail_tower_erpnext_connector/tests/test_foundation.py`: asserts the app is in the site's installed-apps list and that `hooks.py` exposes the required metadata fields (FR-001, FR-002)
- [X] T008 [US1] Write no-business-mutation + no-fork test in `retail_tower_erpnext_connector/tests/test_foundation.py`: asserts the app declares NO DocType that writes product/stock/price/sales data, registers NO document-event/scheduled hooks touching business data (FR-005), and embeds NO copied ERPNext/Frappe core modules (FR-006)

### Implementation for User Story 1

- [X] T009 [US1] ✅ PASS (local dev, 2026-06-04) — `bench --site retail.localhost install-app retail_tower_erpnext_connector` succeeded; app lists as `retail_tower_erpnext_connector 0.1.0`. See [bench-validation.md](./bench-validation.md). (FR-003, SC-001)
- [X] T010 [US1] ✅ PASS (local dev, 2026-06-04) — `bench --site retail.localhost migrate` succeeded (no-op, empty `patches.txt`); ERPNext business data unchanged. See [bench-validation.md](./bench-validation.md). (FR-010, SC-003)

**Checkpoint**: User Story 1 is fully functional — the app installs and is inspectable. This is the MVP.

---

## Phase 4: User Story 2 - Connector Settings placeholder (Priority: P2)

**Goal**: A single, discoverable Connector Settings configuration record exists after install, marked as a placeholder with no active behavior.

**Independent Test**: With the app installed, searching "Connector Settings" in the desk opens exactly one config record; no functional fields are required.

### Tests for User Story 2 ⚠️

- [X] T011 [US2] Write singleton test in `retail_tower_erpnext_connector/tests/test_foundation.py`: asserts `Connector Settings` is a Single DocType and resolves to exactly one record (FR-004, research.md Decision 1) — bench-dependent, same file as T007/T008 so author sequentially

### Implementation for User Story 2

- [X] T012 [US2] Create `retail_tower_erpnext_connector/connector/doctype/connector_settings/connector_settings.json` defining `Connector Settings` as a **Single** DocType (`issingle: 1`) in the `Connector` module, with no functional fields, System Manager read/write permissions only (data-model.md)
- [X] T013 [P] [US2] Create `retail_tower_erpnext_connector/connector/doctype/connector_settings/connector_settings.py` with the `ConnectorSettings(Document)` controller class and NO business logic (data-model.md, FR-005)
- [X] T014 [P] [US2] Create the doctype `__init__.py` files (module, doctype, connector_settings) so the package imports cleanly
- [X] T015 [US2] ✅ PASS (local dev, 2026-06-04) — Connector Settings singleton verified via the passing singleton test in the suite (T020); resolves to one record. See [bench-validation.md](./bench-validation.md). SC-002 (locate settings from docs) is validated via T017 + T021, not here.

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Version & upgrade policy docs (Priority: P3)

**Goal**: Supported ERPNext/Frappe version range and the staging-before-production upgrade sequence are documented and unambiguous.

**Independent Test**: A developer unfamiliar with the project can read the docs and correctly state the supported version range and the required staging-before-production upgrade steps.

### Implementation for User Story 3

- [X] T016 [P] [US3] Write `docs/decisions/version-pin-upgrade-policy.md`: the exact supported ERPNext/Frappe pin (v15 line), and the policy that compatibility is declared/documented not enforced at install (FR-007, research.md Decision 2)
- [X] T017 [P] [US3] Write `docs/runbooks/staging-install.md` as the canonical staging install guide (mirror `quickstart.md`); include the unsupported-version operator action (FR-009, edge case)
- [X] T018 [P] [US3] Write `docs/runbooks/upgrade-compatibility.md`: the upgrade sequence requiring staging validation + rehearsed backup/restore before any production change (FR-008, Constitution III)

**Checkpoint**: All three user stories are independently functional and documented.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-level consistency and final validation across stories.

- [X] T019 [P] Add app entry to repo `README.md` "Current Status" noting 001 foundation is implemented (keep README roadmap accurate); add `.gitignore`
- [X] T020 ✅ PASS (local dev, 2026-06-04) — `bench --site retail.localhost run-tests --app retail_tower_erpnext_connector`: Ran 8 tests in 0.046s, OK. See [bench-validation.md](./bench-validation.md).
- [ ] T021 ⏳ BENCH-VALIDATION (PENDING) — Execute `quickstart.md` end-to-end on a clean site (install → verify table → **uninstall**) and confirm every SC-001..SC-005 checkpoint passes. The uninstall/reinstall data-safety flow has NOT yet been run; install/migrate/tests passed (see [bench-validation.md](./bench-validation.md)) but the full end-to-end remains pending.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–5)**: All depend on Foundational completion.
  - US1 (P1) has no dependency on US2/US3.
  - US2 (P2) depends on the app being installable (US1's install path) to verify the singleton on a site, but its DocType definition (T012–T014) can be authored in parallel with US1.
  - US3 (P3) is pure documentation — fully independent, can run any time after Setup.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Within Each User Story

- Tests (T007/T008/T011) written and failing before implementation.
- `hooks.py` metadata (Phase 2) before install verification (US1).
- DocType JSON before controller before site verification (US2).

### Parallel Opportunities

- T003, T004 (Setup) run in parallel.
- T007, T008, T011 (tests) all write `test_foundation.py` — NOT parallel; author sequentially (no `[P]` marker).
- T013, T014 (US2) parallel with each other.
- T016, T017, T018 (US3 docs) all parallel — different files, no code dependency.
- US3 (docs) can proceed in parallel with US1/US2 entirely.

---

## Parallel Example: User Story 3 (docs)

```bash
# All three docs are independent files — author together:
Task: "Write docs/decisions/version-pin-upgrade-policy.md (T016)"
Task: "Write docs/runbooks/staging-install.md (T017)"
Task: "Write docs/runbooks/upgrade-compatibility.md (T018)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 (US1).
2. **STOP and VALIDATE**: app installs on staging, metadata clear, no business mutation.
3. This is a shippable MVP — the foundation exists and is inspectable.

### Incremental Delivery

1. Setup + Foundational → app package ready.
2. US1 → install works → MVP.
3. US2 → Connector Settings anchor exists.
4. US3 → policy docs complete.
5. Polish → README + full suite + end-to-end quickstart.

---

## Notes

- [P] = different files, no incomplete dependencies.
- Every task names an exact file path.
- The constitutional guardrails (FR-005 no mutation, FR-006 no fork) are enforced by
  T008 (negative test) and by the deliberate absence of business DocTypes/hooks.
- Commit after each task or logical group; do not proceed past a checkpoint with failing tests.
