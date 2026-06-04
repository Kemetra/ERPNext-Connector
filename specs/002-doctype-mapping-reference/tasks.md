---
description: "Task list for the DocType Mapping Reference"
---

# Tasks: DocType Mapping Reference

**Input**: Design documents from `/specs/002-doctype-mapping-reference/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: None. This is a documentation + decision artifact (FR-008); the spec requests no
automated tests. Verification is reviewer review against the acceptance scenarios
(quickstart.md verification table) — a human gate, not a test suite.

**Organization**: Tasks grouped by user story — US1 (build the matrix), US2 (DP2-sourced
verification), US3 (signed decision records).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3
- All paths are relative to the repository root

## Path Conventions

Documentation artifact. Matrix at `docs/architecture/doctype-mapping-reference.md`; decision
records under `docs/decisions/`. Per plan.md "Structure Decision". No code.

---

## Phase 1: Setup

**Purpose**: Create the documentation locations.

- [X] T001 Ensure `docs/architecture/` and `docs/decisions/` directories exist (per README layout; `docs/decisions/` may already exist from spec 001)
- [X] T002 Create the skeleton `docs/architecture/doctype-mapping-reference.md` with title, purpose, a "How to read this matrix" preamble (column meanings from data-model.md), and an empty matrix table header (ERPNext concept | Retail Tower counterpart | Owner of truth | Status | DP2 source citation)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the authoritative-source list and citation rule that every matrix row depends on.

**⚠️ CRITICAL**: The matrix rows (US1) cannot be trusted until the citation policy is fixed.

- [X] T003 In `docs/architecture/doctype-mapping-reference.md`, add a "Sources & precedence" section stating Data-Pulse-2 is authoritative for the Retail Tower side (FR-003), that code/contracts outrank prose (spec Assumption), and that ERPNext is addressed only via generic `{doctype, name}` (FR-004) — citing research.md Decision 1 & 3

**Checkpoint**: Citation policy fixed — matrix rows can now be written with confidence.

---

## Phase 3: User Story 1 - Build the canonical mapping matrix (Priority: P1) 🎯 MVP

**Goal**: A complete matrix row for every listed ERPNext concept with counterpart, owner of truth, status, and DP2 citation.

**Independent Test**: A reviewer reads the matrix and can state the RT counterpart, owner, and status for each of Company, Warehouse, Item, Barcode, UOM, Price List, Sale/Invoice, Payment, Return.

- [X] T004 [US1] Add matrix rows for the **identity & structure** concepts in `docs/architecture/doctype-mapping-reference.md`: Company→`tenants` (`schema/tenants.ts`); Warehouse→`stores` (`schema/stores.ts`). Owner of truth + status (Resolved) per research.md Decision 1
- [X] T005 [US1] Add matrix rows for the **catalog** concepts: Item→`tenant_products` (`schema/catalog/tenant-products.ts`); Item Barcode→`product_aliases` (`schema/catalog/product-aliases.ts`); Price List→`price_history`/`default_price` (`schema/catalog/price-history.ts`, status Resolved — reference only)
- [X] T006 [US1] Add the **UOM** matrix row: free-text `unit`/`stocking_unit`, no DP2 master (`schema/sales/sale-lines.ts`, `schema/inventory/stock-movements.ts`), status **Decision needed** linking to `docs/decisions/mapping-uom.md`
- [X] T007 [US1] Add matrix rows for the **sales** concepts: POS/Sales Invoice→`sales`+`sale_lines` (`schema/sales/sales.ts`, `sale-lines.ts`); Return/Refund→`sale_refunds`+`sale_voids` (`schema/sales/sale-terminal-events.ts`); Payment Entry→not modeled (`pos-payments/vouchers.yaml`), status **Deferred to 006**
- [X] T008 [US1] Add the **Product→Item correlation** row and prose: `erpnext_item_map` (`schema/catalog/erpnext-item-map.ts`, migration `0017_erpnext_item_map.sql`), confirmed-state semantics, 1:1 active invariant — concept level only (FR-009, FR-010)
- [X] T009 [US1] Add the **Customer** row: not modeled in DP2 (walk-in retail), owner = ERPNext, status **Deferred / ERPNext-owned**; note any connector default is a decision (FR-006)

**Checkpoint**: All listed concepts present as rows with status (SC-001). MVP — the matrix is reviewable on its own.

---

## Phase 4: User Story 2 - DP2-sourced verification (Priority: P2)

**Goal**: Every matrix row cites a locatable Data-Pulse-2 source that confirms the named counterpart; no RT concept defined only in this repo.

**Independent Test**: For each row, the cited DP2 path can be opened and confirms the counterpart; ERPNext addressing is generic only.

- [X] T010 [US2] Verify every matrix row's DP2 citation is a real, locatable path in the Data-Pulse-2 repo (`C:\Users\user\Documents\GitHub\Data-Pulse-2`) and confirms the named counterpart; fix any citation that does not resolve (SC-004)
- [X] T011 [US2] Audit the matrix for ERPNext field-level names; confirm ERPNext documents are addressed only via `{doctype, name}` (FR-004); add the `ErpnextDocumentRef` citation (`posting-feed.yaml`)
- [X] T012 [US2] Add a "Superseded sources" note recording that DP2's `docs/ROADMAP-ERP.md` is stale and that schema/contracts are authoritative where prose diverges (FR-007)

**Checkpoint**: Matrix is fully DP2-sourced and version-independent.

---

## Phase 5: User Story 3 - Signed decision records (Priority: P3)

**Goal**: Every "Decision needed" mapping has a decision record with question, options, and a sign-off line; deferrals name their owning spec.

**Independent Test**: Each "Decision needed" row has a record; a planner can tell which decisions are signed vs blocking which spec.

- [X] T013 [P] [US3] Write `docs/decisions/mapping-uom.md`: question (how the connector reconciles DP2 free-text units with ERPNext UOM, given no DP2 UOM master — DP2 013 OQ-3), options, recommendation, **Sign-off** line (open), and `Blocks: 004/006` (FR-005, SC-003)
- [X] T014 [P] [US3] Write `docs/decisions/mapping-customer.md`: question (does posting need a connector default Customer, or is it ERPNext-owned for walk-in retail), options, **Sign-off** line (open), `Blocks: 006` (FR-005)
- [X] T015 [US3] In the matrix, confirm every `Deferred` concept (Payment, Customer, tax) names its owning later spec (FR-006); cross-link each `Decision needed` row to its decision record

**Checkpoint**: All ambiguous mappings are recorded as decisions; downstream gating is explicit.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency and reviewer-readiness.

- [X] T016 [P] Update `README.md` "Current Status" to note spec 002 mapping reference is drafted and point to `docs/architecture/doctype-mapping-reference.md`
- [X] T017 Run the quickstart verification checklist end-to-end against the finished reference (all concepts present, citations locate, decisions have sign-off, deferrals name owner) and confirm SC-001..SC-005 pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — the citation policy (T003) BLOCKS trusting the matrix rows.
- **US1 (Phase 3)**: Depends on Foundational — writes the rows.
- **US2 (Phase 4)**: Depends on US1 — verifies the rows it produced.
- **US3 (Phase 5)**: Depends on US1 (needs the "Decision needed" rows identified); the decision-record files (T013/T014) can be drafted in parallel with US2.
- **Polish (Phase 6)**: Depends on US1–US3.

### Within / Across Stories

- T004–T009 (US1) all edit the same matrix file → author sequentially (no `[P]`).
- T013, T014 (US3) are separate decision-record files → `[P]`.
- US3 decision drafts can overlap US2 verification (different files).

### Parallel Opportunities

- T013 + T014 (two decision records, different files) run in parallel.
- T016 (README) is independent of the decision records.
- US1 row tasks are NOT parallel (one shared matrix file).

---

## Parallel Example: User Story 3 (decision records)

```bash
# Two decision records are independent files — draft together:
Task: "Write docs/decisions/mapping-uom.md (T013)"
Task: "Write docs/decisions/mapping-customer.md (T014)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (citation policy) → Phase 3 (US1 matrix).
2. **STOP and VALIDATE**: every listed concept has a row with status (SC-001).
3. The matrix is a reviewable deliverable on its own — MVP.

### Incremental Delivery

1. Setup + Foundational → citation policy fixed.
2. US1 → matrix complete → MVP.
3. US2 → every row DP2-sourced & verified.
4. US3 → ambiguous mappings recorded as signed-able decisions.
5. Polish → README + end-to-end quickstart verification.

---

## Notes

- [P] = different files, no dependencies.
- This feature produces NO code (FR-008) — only the matrix and decision records.
- The constitutional guardrails are FR-003 (cite DP2, Principle I) enforced by T003/T010,
  and FR-004 (generic `{doctype,name}`, Principle II) enforced by T011.
- Commit after each phase or logical group.
