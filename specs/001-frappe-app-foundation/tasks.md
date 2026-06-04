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

- [ ] T001 Create app package directory structure per plan.md: `retail_tower_erpnext_connector/` with nested `retail_tower_erpnext_connector/doctype/`, and a top-level `tests/` and `docs/` (`docs/runbooks/`, `docs/decisions/`)
- [ ] T002 Create `pyproject.toml` at repo root with app packaging metadata, SemVer version `0.1.0`, and the supported version pin (`frappe`, `erpnext` v15 line) per FR-007 and research.md Decision 2
- [ ] T003 [P] Create `retail_tower_erpnext_connector/modules.txt` declaring the `Connector` module
- [ ] T004 [P] Create empty `retail_tower_erpnext_connector/patches.txt` (no migrations at foundation, per data-model.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: App metadata and module wiring that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Create `retail_tower_erpnext_connector/hooks.py` with app metadata (`app_name`, `app_title` "Retail Tower ERPNext Connector", `app_publisher` "Retail Tower OS", `app_description`, `app_license` per repo LICENSE) per FR-002; register NO document-event hooks, scheduled jobs, or overrides (FR-005)
- [ ] T006 [P] Create `retail_tower_erpnext_connector/__init__.py` exposing `__version__` consistent with `pyproject.toml`

**Checkpoint**: App package is metadata-complete and installable as an empty app — user story implementation can now begin.

---

## Phase 3: User Story 1 - Install on staging ERPNext site (Priority: P1) 🎯 MVP

**Goal**: The app installs cleanly on a staging ERPNext site, loads without error, shows clear metadata, and changes no ERPNext business data.

**Independent Test**: On a fresh staging site, `bench install-app retail_tower_erpnext_connector` succeeds, the app appears in `list-apps`, the desk loads, and product/stock/sales counts are unchanged.

### Tests for User Story 1 ⚠️

> Write these FIRST, ensure they FAIL before implementation (no app installed yet).

- [ ] T007 [P] [US1] Write install + metadata test in `retail_tower_erpnext_connector/tests/test_foundation.py`: asserts the app is in the site's installed-apps list and that `hooks.py` exposes the required metadata fields (FR-001, FR-002)
- [ ] T008 [P] [US1] Write no-business-mutation test in `retail_tower_erpnext_connector/tests/test_foundation.py`: asserts the app declares NO DocType that writes product/stock/price/sales data and registers NO document-event/scheduled hooks touching business data (FR-005)

### Implementation for User Story 1

- [ ] T009 [US1] Verify `hooks.py` metadata renders correctly via `bench --site <staging> install-app retail_tower_erpnext_connector` on a staging site; confirm install succeeds and the app lists (FR-003, SC-001)
- [ ] T010 [US1] Run `bench --site <staging> migrate` and confirm it is a no-op (empty `patches.txt`), then confirm the desk loads and ERPNext business data is unchanged (FR-010, SC-003)

**Checkpoint**: User Story 1 is fully functional — the app installs and is inspectable. This is the MVP.

---

## Phase 4: User Story 2 - Connector Settings placeholder (Priority: P2)

**Goal**: A single, discoverable Connector Settings configuration record exists after install, marked as a placeholder with no active behavior.

**Independent Test**: With the app installed, searching "Connector Settings" in the desk opens exactly one config record; no functional fields are required.

### Tests for User Story 2 ⚠️

- [ ] T011 [P] [US2] Write singleton test in `retail_tower_erpnext_connector/tests/test_foundation.py`: asserts `Connector Settings` is a Single DocType and resolves to exactly one record (FR-004, research.md Decision 1)

### Implementation for User Story 2

- [ ] T012 [US2] Create `retail_tower_erpnext_connector/retail_tower_erpnext_connector/doctype/connector_settings/connector_settings.json` defining `Connector Settings` as a **Single** DocType in the `Connector` module, with no functional fields (at most a non-functional placeholder note), System Manager read/write permissions only (data-model.md)
- [ ] T013 [P] [US2] Create `retail_tower_erpnext_connector/retail_tower_erpnext_connector/doctype/connector_settings/connector_settings.py` with the controller class and NO business logic (data-model.md, FR-005)
- [ ] T014 [P] [US2] Create the doctype `__init__.py` files so the DocType package imports cleanly
- [ ] T015 [US2] Reinstall/migrate on staging and confirm exactly one Connector Settings record exists and opens, and a second install does not duplicate it (US2 acceptance, reinstall edge case)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Version & upgrade policy docs (Priority: P3)

**Goal**: Supported ERPNext/Frappe version range and the staging-before-production upgrade sequence are documented and unambiguous.

**Independent Test**: A developer unfamiliar with the project can read the docs and correctly state the supported version range and the required staging-before-production upgrade steps.

### Implementation for User Story 3

- [ ] T016 [P] [US3] Write `docs/decisions/version-pin-upgrade-policy.md`: the exact supported ERPNext/Frappe pin (v15 line), and the policy that compatibility is declared/documented not enforced at install (FR-007, research.md Decision 2)
- [ ] T017 [P] [US3] Write `docs/runbooks/staging-install.md` as the canonical staging install guide (mirror `quickstart.md`); include the unsupported-version operator action (FR-009, edge case)
- [ ] T018 [P] [US3] Write `docs/runbooks/upgrade-compatibility.md`: the upgrade sequence requiring staging validation + rehearsed backup/restore before any production change (FR-008, Constitution III)

**Checkpoint**: All three user stories are independently functional and documented.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-level consistency and final validation across stories.

- [ ] T019 [P] Add app entry to repo `README.md` "Current Status" noting 001 foundation is implemented (keep README roadmap accurate)
- [ ] T020 Run the full foundation test suite via `bench --site <staging> run-tests --app retail_tower_erpnext_connector` and confirm all tests pass
- [ ] T021 Execute `quickstart.md` end-to-end on a clean staging site (install → verify table → uninstall) and confirm every SC-001..SC-005 checkpoint passes

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
- T007, T008 (US1 tests) run in parallel — same file, but additive test functions; if authored separately, sequence them.
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
