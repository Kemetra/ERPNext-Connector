---
description: "Task list — Receivables & Third-Party Posting Adapter (Connector 009)"
---

# Tasks: Receivables & Third-Party Posting Adapter

**Input**: Design documents from `specs/009-receivables-and-third-party-posting-adapter/`

**Prerequisites**: spec.md (required; user stories + FRs), plan.md (required; phased
approach + gate plan). No `data-model.md` / `contracts/` — the data model is
**upstream** (`settlement.yaml` G2 + the future 012 settlement extension); 009
authors no contract or OpenAPI.

**Status**: Proposed / Draft. **NO code is authored in this artifact.** This is an
ordered, gate-tagged task list for the OWNING repo
(`Retail-Tower-ERP-Next-Connector`) to execute **after dispatch**, *behind* the two
hard upstream blockers (012 settlement extension; 011-DR-POSTING-R1). It marks **no**
gate satisfied and lifts **no** rider.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency).
- **[Story]**: US1 / US2 / US3 from spec.md, or `INFRA` / `GATE`.
- **(dep: …)**: task dependency.
- **Gate tags** use the connector cross-repo vocabulary (G2 / G3 / G10 / G4) +
  the **011-DR-POSTING-R1** rider — distinct from DP-2 035's work-package G-letters.

## Path Conventions

- Single Frappe-app project: `retail_tower_erpnext_connector/posting/` (the existing
  posting transport + sale-post adapter from connector `006`). The settlement posting
  path is an **additive branch** on that surface (plan §Project Structure).

> **These tasks define the contract-consuming work, not implementation steps that
> write code.** No task here authors connector/Frappe code, `hooks.py`, OpenAPI,
> DocType, or migration. Code-writing happens only post-dispatch, after T0 clears.

---

## Phase 0 (T0): Upstream gate preconditions (NO code; HARD blockers)

**Purpose**: nothing in Phases 1+ may start until these clear. NONE is satisfied by
this artifact.

- [ ] **T001 [GATE]** [OQ-1 / CRITICAL-1] Confirm DP-2 has authored & ratified the
  **versioned, backward-compatible 012 posting-feed extension** carrying the approved
  settlement / cash-application / claim / remittance command (a new
  `PostingWorkItem.kind` + `erpnextPaymentEntryRef` / tender fields). Today the 012
  `kind` enum is `[sale_post, reversal]` only (spec E-4). **Blocker if absent — there
  is nothing to pull.** 009 authors **none** of this extension. *(spec OQ-1, FR-015)*
- [ ] **T002 [GATE]** [OQ-2] Confirm the owner has **lifted 011-DR-POSTING-R1** for
  the ERPNext **Payment-Entry** posting (DP-2 035 §OQ-7). **Blocker on FR-001.**
  *(dep: T001)*
- [ ] **T003 [GATE][G2]** Re-read DP-2 `origin/main` at dispatch: confirm
  `settlement.yaml` (G2, RATIFIED) and the 012 extension still match the spec's
  Evidence basis (snapshot, not live view). *(dep: T001)*
- [ ] **T004 [GATE][G10]** Verify 028 boundary decisions are signed and G10 is
  verified for this `connector`-scoped consumer (spec §8); confirm posting reuses the
  `connectorBearer` scheme (no new credential, NG-7). *(dep: T003)*

---

## Phase 1 (US1, P1): Post an approved cash application as an ERPNext Payment Entry

**Goal (spec US1, FR-001/FR-002/FR-003/FR-007)**: the deferred-from-006 core — one
Payment Entry per approved cash application, acked with the document ref.

- [ ] **T005 [US1][G2]** Define the consumption mapping: the future 012 settlement
  work-item kind (T001) → an ERPNext **Payment Entry** against the **existing** Sales
  Invoice that connector `006` posted, addressed generically `{doctype, name}`
  (FR-001/FR-009). **No re-post or edit of the invoice** (NG-5). *(dep: T001, T002)*
- [ ] **T006 [US1]** Define the ack contract realization: the posted Payment Entry's
  ERPNext document ref is returned via `connectorAckOutcome` so DP-2 can populate
  `Receivable.erpnextPaymentEntryRef` (FR-002). *(dep: T005)*
- [ ] **T007 [US1]** Define partial cash application → a partial Payment Entry
  consistent with the upstream `partially_applied` receivable state, invoice left
  partially outstanding (FR-003). *(dep: T005)*
- [ ] **T008 [US1]** Define idempotency realization over the 012 ack semantics:
  re-pulled / re-acked work-item → **no duplicate** Payment Entry; key reused with a
  different outcome → `idempotency_key_conflict` (FR-007, G5). *(dep: T006)*
- [ ] **T009 [US1]** Define the "apply, never resolve" posture: the Payment Entry
  applies DP-2-pre-resolved references (account / payer) only; resolves nothing
  (FR-010, NG-8; connector `006` rider R2–R5). *(dep: T005)*

---

## Phase 2 (US2, P2): Post a claim / remittance reconciliation valuation

**Goal (spec US2, FR-004)**: post the ERPNext valuation movement for a reconciled
`ReconciliationResult`.

- [ ] **T010 [US2][G2]** Define the consumption mapping: an approved
  reconciliation command (`consoleReconcileRemittance` → `ReconciliationResult` of
  `settled | partial | flagged`) → the matching ERPNext valuation movement against
  the claimed receivable(s) (FR-004). *(dep: T005)*
- [ ] **T011 [US2]** [OQ-3] Decide the exact ERPNext valuation document (Payment
  Entry vs Journal Entry vs credit/debit note) for a claim/remittance — a design-time
  mapping decision; frame conceptually, do not pre-build. *(dep: T010; spec OQ-3)*
- [ ] **T012 [US2]** Define the three reconciliation outcomes: `settled` clears the
  receivable(s) (variance zero); `partial` records the remitted amount + variance;
  `flagged` → a deterministic safe posting outcome, never indeterminate (DP-2 035 §4
  edge cases). *(dep: T010)*

---

## Phase 3 (US3, P3): Rejected line / reversal routes via Arc A (reuse; NO new model)

**Goal (spec US3, FR-005, NG-1)**: a rejection / reversal reuses Connector Arc A.

- [ ] **T013 [US3]** Define the routing rule: a rejected claim line / reversal posts
  a **NEW reversing document** via the existing **Connector Arc A** forward-feed
  reversal (the 012 `kind: reversal` work-item) + DP-026 + POS-014. 009 defines
  **no** competing reversal posting kind (FR-005, NG-1). *(dep: T010)*
- [ ] **T014 [US3]** [OQ-4] Document how a receivable 009 posted a Payment Entry for
  **consumes** a later DP-026 reversal (the §OQ-4 CARVE; reversal-compatibility
  fields deferred upstream until DP-026 closes) — Arc A reuse only, never a 009-side
  re-derivation. *(dep: T013; spec OQ-4)*

---

## Phase 4: Idempotency, audit, observability, tax-pending, isolation (cross-cutting)

**Goal (FR-007/011/012/013/014)**: the non-functional posture across all kinds.

- [ ] **T015** Define the failure posture: a permanent ERPNext rejection (closed
  period / unmapped account / validation) acks `permanently_rejected` with a
  structured reason (012 vocabulary); DP-2 owns the resulting DLQ / reconciliation
  state — 009 never silently drops a work-item (FR-012). *(dep: T008)*
- [ ] **T016 [G4]** Define the audit + observability posture: every posting attempt
  records work-item ref / ERPNext document ref / outcome / time; posting-health
  signals emitted; **secrets never logged** (FR-013, conform to 003 G4). *(dep: T015)*
- [ ] **T017** Define tax-pending posting: carry the placeholder verbatim, compute
  **no** VAT allocation (FR-011, NG-4); and tenant/store scoping via the
  `connectorBearer` principal — cross-tenant ref → non-disclosing `not_found`
  (FR-014, §II/§XII). *(dep: T005)*
- [ ] **T018 [G3]** Identify (conceptually only) any additive **Frappe `Connector
  Settings` DocType** delta for settlement-posting enablement — a `bench migrate`
  DocType change, **not** SQL (G3 discipline). **No DocType authored here** (NG-3,
  spec §7). *(dep: T001)*

---

## Phase 5: Documentation closeout (owning-repo docs; post-dispatch; no gate)

- [ ] **T019** Update the connector's own decision/runbook docs (post-dispatch) to
  record that the deferred-from-006 Payment Entry now posts, keyed to the 012
  settlement extension, plus the 006↔009 carve. **Owning-repo docs, not authored
  here.** *(dep: T015, T012, T013)*

---

## Open-question tasks (do NOT pre-decide — carry to owner)

- [ ] **T-OQ1 [GATE / CRITICAL]** Owner/DP-2 decide & ratify the **012 settlement
  work-item extension** shape + `kind` (the contract surface 009 consumes). *(spec
  OQ-1; blocks T005+)*
- [ ] **T-OQ2 [GATE / CRITICAL]** Owner decide whether to **lift 011-DR-POSTING-R1**
  for the Payment-Entry posting. *(spec OQ-2; blocks FR-001)*
- [ ] **T-OQ3** Decide the ERPNext claim/remittance valuation document shape. *(spec
  OQ-3; T011)*
- [ ] **T-OQ4** Decide reversal-consumed sequencing (Arc A reuse; deferred upstream
  until DP-026 closes). *(spec OQ-4; T014)*

---

## Dependencies & sequencing

- **Hard upstream blockers (Phase 0):** T001 (012 extension) + T002 (011-DR-POSTING-R1)
  gate **everything**. T003/T004 (G2 re-read, G10 verify) before any consumption work.
- **Story order:** US1 (T005–T009) → US2 (T010–T012) → US3 (T013–T014). US1 is the
  P1 MVP (the deferred-from-006 Payment Entry); US2/US3 layer on it.
- **Cross-cutting (Phase 4):** T015–T018 ride the posting paths; T016 (audit) and
  T017 (tax/isolation) are [P] against each other (different concerns).
- **Carve invariant (all phases):** 006 owns the Sales Invoice; 009 adds the Payment
  Entry / claim valuation — never double-posts (NG-5). Reversal = Arc A reuse, no new
  model (NG-1). Consume via 012 only; never call `settlement.yaml` Console/POS (FR-006).

## Gate tag summary

| Phase | Tasks | Gate tags | Note |
|-------|-------|-----------|------|
| 0 Preconditions | T001–T004 | OQ-1, OQ-2 (011-DR-POSTING-R1), G2, G10 | All hard blockers; NONE satisfied. |
| 1 Payment Entry (US1) | T005–T009 | G2 (consume), 011-DR-POSTING-R1 (gated) | Deferred-from-006 core. |
| 2 Claim valuation (US2) | T010–T012 | G2 (consume) | OQ-3 design mapping. |
| 3 Reversal routing (US3) | T013–T014 | — | Arc A reuse (NG-1); no new model. |
| 4 Cross-cutting | T015–T018 | G4 (adjacent), G3 (DocType id only) | Idempotency / audit / tax / isolation. |
| 5 Docs closeout | T019 | — | Owning-repo docs only. |

---

> **SPECIFY/plan/tasks record (Proposed / Draft).** No code, contract, migration, or
> DocType is authored in this task list. Dispatch of any task requires explicit
> scoped owner approval after the Phase 0 upstream preconditions (012 settlement
> extension + 011-DR-POSTING-R1) clear and G10 is verified.
