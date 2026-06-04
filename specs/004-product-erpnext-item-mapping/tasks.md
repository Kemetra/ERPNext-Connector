---
description: "Task list for Product–ERPNext Item Mapping (Posting Resolution)"
---

# Tasks: Product–ERPNext Item Mapping (Posting Resolution)

**Input**: Design documents from `/specs/004-product-erpnext-item-mapping/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: None. This is a documentation + policy artifact (Principle VII; no connector code — the
resolution/UOM-map/posting code lands in spec 006). Verification is reviewer review against the
acceptance scenarios (quickstart.md). Bench resolution (SC-006) is deferred (no local bench;
standing-rules §6) and also depends on DP2 holding confirmed mappings.

**Organization**: Tasks grouped by user story — US1 (resolve to Item), US2 (confirmed-only
invariant), US3 (fail-closed unresolved surfacing — co-equal P1), US4 (UOM + money). The policy is
ONE document; the US sections all edit it, so those tasks are sequential (not `[P]`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 / US4
- All paths are relative to the repository root

## Path Conventions

Documentation artifact. Policy at `docs/decisions/product-item-mapping-resolution.md` (per
plan.md). The signed ad-hoc-line decision folds INTO this doc (intra-spec). No separate decision
record, no `contracts/` (DP2 owns the contracts), no code.

---

## Phase 1: Setup

**Purpose**: Create the resolution-policy document skeleton.

- [ ] T001 Ensure `docs/decisions/` exists (created in spec 002); create the skeleton `docs/decisions/product-item-mapping-resolution.md` with title, status, purpose, and section headers: Sources & precedence, Resolution direction, Resolution input (confirmed item-map), Resolution decision table, Unresolved outcomes & reason mapping, UOM & money, Idempotency & replay, Secrets & correlation
- [ ] T002 In the skeleton, add the **Sources & precedence** section: Data-Pulse-2 is authoritative (cite, don't redefine — FR-013, Principle I); code/contracts over prose; spec 004 resolves DP2-product → ERPNext-Item and does NOT export catalog from ERPNext (cite research.md Decision 1: `posting-feed.yaml` two-op surface, `AUTO_MATCH_NO_SOURCE`/OQ-8, `read-down.yaml` catalog authority, G4 reverse-direction bar)

---

## Phase 2: User Story 1 - Resolve a sale-line's product to an ERPNext Item (Priority: P1) 🎯 MVP

**Goal**: The policy documents how `tenantProductRef` resolves to a confirmed ERPNext Item, addressed generically as `{doctype, name}`.

**Independent Test**: A reviewer can trace a confirmed-mapping sale line to exactly one ERPNext Item reference, addressed generically, from the Resolution-input + decision-table sections alone.

- [ ] T003 [US1] Write the **Resolution direction** section in `docs/decisions/product-item-mapping-resolution.md`: the connector consumes the confirmed DP2 mapping at posting time; it neither exports ERPNext catalog nor calls DP2's review surface; cite `posting-feed.yaml` `tenantProductRef` lines 481–484 ("The connector maps it to an ERPNext Item (013) behind this contract") (FR-001)
- [ ] T004 [US1] Write the **Resolution input** section: resolve via DP2 `erpnext_item_map` (spec 013, migration 0017); read only `state = confirmed` AND `retired_at = null`; output the resolved Item as generic `{doctype: "Item", name: erpnext_item_ref}` (FR-001, FR-002, Principle II); cite `catalog/erpnext-item-map.yaml` + `ErpnextDocumentRef` (O-6, generic addressing)

**Checkpoint**: The happy-path resolution (confirmed mapping → single generic Item) stands on its own — MVP.

---

## Phase 3: User Story 3 - Surface unresolved products explicitly, never silently (Priority: P1, co-equal) 🎯 MVP

**Goal**: The policy documents the fail-closed unhappy path — the spine of the spec (Principle VI). Authored alongside US1 because resolution is only complete when BOTH terminal states are defined.

**Independent Test**: A reviewer confirms every unresolved input condition lands in a typed `permanently_rejected` outcome with the correct closed `reason.category`, and that no silent guess/drop/catch-all path exists.

- [ ] T005 [US3] Write the **Resolution decision table** section: reproduce data-model.md's 8-condition table (confirmed→posted; null/no-mapping/suggested/retired/double-confirmed/Item-absent→unmapped_item; unmapped-UOM→validation); assert the binary invariant (`posted` XOR `permanently_rejected`, no third path) (FR-006, SC-001)
- [ ] T006 [US3] Write the **Unresolved outcomes & reason mapping** section: every unresolved case is `outcome = permanently_rejected`; map product cases → `reason.category = unmapped_item` and unmapped-UOM → `validation` (NO `unmapped_uom` exists; no new wire reason invented) (FR-006, FR-007, SC-003); cite `posting-feed.yaml` `OutcomeAckRequest` + `RejectionReason` closed set
- [ ] T007 [US3] Add the **no-self-retry / DP2-owns-reconciliation** rule: the connector reports `permanently_rejected` and does NOT invent a `failed_transient` loop; DP2 owns DLQ + 017 reconciliation; the policy cites `dlqueued` + the 017 flag and asserts NO re-drive mechanism it cannot see (FR-006, research.md Decision 4); the original DP2 sale fact is never mutated (FR-007, O-3)
- [ ] T008 [US3] Add the **ad-hoc line** rule (signed, intra-spec): a null `tenantProductRef` fails closed as `permanently_rejected` / `unmapped_item`; NO catch-all Item; record the 2026-06-04 Option-A sign-off line here (FR-012, SC-005)

**Checkpoint**: Both terminal states defined — the resolution policy is complete and binary (US1 + US3 together = the MVP).

---

## Phase 4: User Story 2 - Honor the confirmed-only invariant and lifecycle (Priority: P2)

**Goal**: The policy documents that only confirmed, non-retired mappings resolve, and that the connector consumes (never owns) DP2 spec 013's lifecycle.

**Independent Test**: A reviewer can state that `suggested`/`retired`/double-confirmed mappings are treated as unresolved, and that the connector never calls the `cookieAuth` review surface.

- [ ] T009 [US2] Write the **Confirmed-only invariant & lifecycle** section: only `state = confirmed`, `retired_at = null` resolves; `suggested`/`retired` route to unresolved (US3); the connector relies on the 1:1 active invariant (OQ-2) and treats two confirmed mappings as fail-closed (never pick one) (FR-003); cite item-map confirmed-only invariant (data-model §3) + lifecycle
- [ ] T010 [US2] Add the **lifecycle ownership** rule: suggest/confirm/retire is a human Tenant-Admin action via `cookieAuth` (Retail-Tower-Console), explicitly NOT the `connectorBearer` machine scheme; the connector neither builds nor calls it, and invents no auto-match source (`AUTO_MATCH_NO_SOURCE`, OQ-8) — never creates/searches ERPNext Items (FR-004, FR-005, Principle I); cite item-map auth boundary

**Checkpoint**: The invariant + ownership documented; US2 stands on the US1/US3 resolution base.

---

## Phase 5: User Story 4 - Reconcile UOM and money per signed decisions (Priority: P3)

**Goal**: The policy documents unit→UOM reconciliation (signed Option A) and exact-decimal money.

**Independent Test**: A reviewer can state that an unmapped unit fails closed as `validation`, and that money is exact-decimal + ISO-4217, from the UOM & money section.

- [ ] T011 [US4] Write the **UOM & money** section: reconcile DP2 free-text `unit` per signed `docs/decisions/mapping-uom.md` (Option A: connector-side unit→ERPNext-UOM map); an unmapped unit fails closed as `permanently_rejected` / `validation` (FR-008); money is exact-decimal string + ISO-4217 `currency_code`, never float (FR-009); cite `mapping-uom.md` + `posting-feed.yaml` `DecimalAmount`/`CurrencyCode`

**Checkpoint**: All four stories complete; the resolution policy is whole.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Idempotency/correlation cross-cuts, citation verification, reviewer-readiness.

- [ ] T012 Write the **Idempotency & replay** section (documented-not-implemented): replay key `sourceSystem + externalId` → same ERPNext document; WHEN DP2 re-offers a previously `unmapped_item` work-item after confirmation, resolution + post is idempotent (no duplicate); the re-offer decision is DP2's (Principle IV applies in spec 006) (FR-010); cite `posting-feed.yaml` O-3 + idempotency replay
- [ ] T013 Write the **Secrets & correlation** section: unresolved/error outcomes traceable via the spec-003 DP2 `request_id`; NO secrets/tokens/credentials in logs, errors, or UI (FR-011, gate G4, Principle V); `reason.message` carries no sensitive ERPNext internals
- [ ] T014 Verify every DP2 citation in the policy + research.md resolves in `C:\Users\user\Documents\GitHub\Data-Pulse-2` and confirms the claim; fix any that does not resolve (FR-013, SC-002)
- [ ] T015 [P] Update `README.md` "Current Status" to note spec 004 resolution policy is drafted and point to `docs/decisions/product-item-mapping-resolution.md`; record the reframe (identity mapping, not catalog export) and that the ad-hoc decision is signed; note spec 006 inherits the resolution policy
- [ ] T016 Run the quickstart verification checklist end-to-end (review-time checks 1–7) against the finished policy and confirm SC-001..SC-005 pass; SC-006 marked deferred (staging bench + DP2 confirmed mappings)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **US1 (Phase 2) + US3 (Phase 3)**: Depend on Setup. Co-equal P1 — together they define BOTH
  terminal states; the resolution policy is incomplete with only one. (US1 = happy path; US3 =
  fail-closed spine.)
- **US2 (Phase 4)**: Depends on US1/US3 (the invariant constrains the resolution base).
- **US4 (Phase 5)**: Depends on US1/US3 (UOM applies to a resolved line; unmapped-unit reuses the
  US3 fail-closed outcome).
- **Polish (Phase 6)**: Depends on US1–US4.

### Within / Across Stories

- T002–T013 all edit the same policy file → author sequentially (no `[P]`).
- T015 (README) is a separate file → `[P]` relative to the policy edits.

### Parallel Opportunities

- T015 (README) is independent of the policy edits.
- The US1/US2/US3/US4 sections are NOT parallel (one shared policy file).

---

## Implementation Strategy

### MVP First (US1 + US3 — the binary resolution)

1. Phase 1 Setup → Phase 2 (US1 happy path) → Phase 3 (US3 fail-closed spine).
2. **STOP and VALIDATE**: every sale-line condition lands in exactly one of two terminal states
   (`posted` XOR `permanently_rejected`), with no silent path.
3. This is the MVP — the resolution policy is reviewable and provably binary.

### Incremental Delivery

1. Setup → policy skeleton + Sources & precedence.
2. US1 + US3 → resolution direction/input + decision table + unresolved outcomes + ad-hoc → MVP.
3. US2 → confirmed-only invariant + lifecycle ownership.
4. US4 → UOM + money.
5. Polish → idempotency/correlation + citation verification + README + end-to-end quickstart.

---

## Notes

- [P] = different files, no dependencies.
- This feature produces NO code (Principle VII) — only the resolution policy document. The
  resolution/UOM-map/posting code lands in spec 006.
- Constitutional anchors: FR-001/FR-013 (cite DP2, Principle I) via T002/T003/T004/T014; FR-002
  (generic addressing, Principle II) via T004; FR-006/007/008/012 (fail-closed surfacing,
  **Principle VI — the spine**) via T005–T008/T011; FR-010 (idempotent, documented; Principle IV
  applies in spec 006) via T012; FR-011 (secrets + correlation, Principle V / gate G4) via T013.
- The ad-hoc-line decision is signed (Clarifications) and recorded in the policy (T008) — spec 006
  inherits no open mapping decision.
- SC-006 (bench resolution) is deferred — needs a staging ERPNext v15 site AND DP2 holding
  confirmed mappings (a DP2-side data-readiness dependency, tracked outside this slice graph).
