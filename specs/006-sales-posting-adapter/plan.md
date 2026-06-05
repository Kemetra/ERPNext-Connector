# Implementation Plan: Sales Posting Adapter (Posting Model & Contract-First Gate)

**Branch**: `feat/con-006-sales-posting-adapter-plan` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-sales-posting-adapter/spec.md`

> **Lane note (§0 / follow-up §4 reconciliation).** Spec 006's merged `spec.md` §0 and
> `follow-up-notes.md` §4 state this spec "ships with companion documents but no `plan.md`" and
> list `plan.md` as "NOT authored (out of this lane)". Those statements describe the **spec-authoring
> lane** (PR #14) — they are **not** a permanent exclusion. Spec.md §0 itself names "the connector's
> own Spec-Kit chain (`plan.md` → Constitution Check → any `[GATED]` schema → `tasks.md` →
> `execution-map.yaml`)" as the gate implementation stays blocked behind. **This document is that
> deferred plan-lane slice.** It authors no code and touches no merged artifact (§0/§4 stay
> verbatim); it advances 006 by one Spec-Kit step (specify → **plan**).

## Summary

Produce the reviewed **plan-lane artifact** for connector spec 006 — the contract-first planning gate
(Principle VII) that precedes any posting code. The Sales Posting Adapter turns a Data-Pulse-2 posting
work-item (a validated 008 sale projection delivered over the fixed 012 posting-feed contract) into an
ERPNext sales document, and acks a typed outcome back to DP2.

The item-identity posture is **apply-only** (rider `011-DR-POSTING-R1` R2 / `Q-CON-004`): DP2
pre-resolves each line's ERPNext Item at work-item projection and carries a **required**
`erpnextItemRef` (`{doctype:"Item", name}`) on every offered line; the connector **applies** it and
performs **no** resolution, lookup, DP2-reachback, or caching. The spec's spine is the **unhappy
path**: every work-item reaches exactly one terminal outcome over `connectorAckOutcome` —
`posted` (one submitted ERPNext document + `documentRef`) XOR `failed_transient` XOR
`permanently_rejected` (with a `reason.category` from DP2's **closed** set) — never a silent partial,
guess, drop, or catch-all Item (Principle VI). The first implementation slice is the **interim
"submitted Sales Invoice / outstanding-AR only" mode** (rider R1); Payment Entry is the **gated**
sub-scope (signed target SI + PE, deferred).

Documentation + planning artifact only: **no connector code, no `hooks.py` edit, no OpenAPI authoring,
no migration** (Principle VII; resolution/poster/idempotency-store land in later, separately-gated
implementation slices). The plan **cites** DP2's authoritative contracts; it does not re-derive them.

## Technical Context

**Language/Version**: N/A — Markdown planning artifact. (Future posting code is Python / Frappe v15
per spec 001; produced in a later implementation slice, not here.)

**Primary Dependencies**: Data-Pulse-2 backend (`C:\Users\user\Documents\GitHub\Data-Pulse-2`) as the
authoritative read-only reference:
- `packages/contracts/openapi/erpnext-connector/posting-feed.yaml` (`1.1.0-draft`, DP2-owned) — the
  fixed two-operation surface `connectorPullPostings` / `connectorAckOutcome`; `PostingWorkItem` /
  `SaleLine` with the **required** `erpnextItemRef`; the outcome enum
  (`posted | failed_transient | permanently_rejected`) and `RejectionReason.category` closed set
  (`validation | closed_period | unmapped_item | unmapped_account | other`); `DecimalAmount` /
  `CurrencyCode`; the `sourceSystem`+`externalId` O-3 idempotency anchor; generic `{doctype, name}`
  addressing (O-6).
- `specs/011-erpnext-pos-reference-and-integration-foundation/decisions/posting-decision-rider-2026-06-05.md`
  (`011-DR-POSTING-R1`, **SIGNED**, R1–R5) — the authoritative posting model: DP2-side item
  resolution (R2), no-substitute-item (R3), unknown-item≠unmapped (R4), warehouse fails-to-DLQ (R5),
  Payment-Entry gating + interim AR-only (R1).
- `specs/015-pos-sale-posting-to-erpnext/` — the DP2 sale-posting spec arc (cited to bound scope).

**Storage**: N/A for this planning artifact. (A connector-side idempotency/dedup store and the
unit→UOM map are later-slice implementation concerns; the plan states the *requirement*, not the
mechanism.)

**Testing**: Reviewer verification against the spec's acceptance scenarios + DP2 citation-locates
(already enumerated in [resolution-concepts.md §7](./resolution-concepts.md)). No automated tests for
a planning artifact. Bench posting (SC-008) is a deferred staging validation (no local bench;
standing-rules §6) and additionally depends on the inherited DP-015 arc gates.

**Target Platform**: N/A (planning document under `specs/006-sales-posting-adapter/`).

**Project Type**: Documentation / planning (single project).

**Performance Goals**: N/A.

**Constraints**: Apply pre-resolved `erpnextItemRef`, never resolve/look-up/reach-back/cache item
identity (FR-001/FR-003, rider R2 / `Q-CON-004`); generic `{doctype, name}` addressing (FR-002,
Principle II); fixed DP2-owned 012 contract, author no OpenAPI (FR-015, Principle I); idempotent on
`sourceSystem`+`externalId`, no new idempotency primitive (FR-005, Principle IV / Gate G5); typed
terminal outcome, closed `RejectionReason` set, no silent partial/guess/drop (FR-006/007,
Principle VI); signed UOM decision Option A, unmapped unit → `validation` fail-closed (FR-008);
exact-decimal + ISO-4217 money, never float (FR-009); apply pre-resolved warehouse, never guess
(FR-010, rider R5); observable + correlated via DP2 `request_id`, no secret leak (FR-012,
Principle V / Gate G4/G7); `hooks.py` stays empty at this layer — poller is a *planned*
`scheduler_event` only (FR-014); docs-only (Principle VII).

**Scale/Scope**: One planning artifact (`plan.md`) plus the already-authored companion docs
(`resolution-concepts.md`, `follow-up-notes.md`). No data volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial evaluation (pre-design):**

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Data-Pulse-2 is the only orchestration boundary | ✅ Pass | The connector consumes the fixed DP2-owned 012 posting-feed over the two-operation pull/ack surface; it authors no OpenAPI (FR-015) and never reaches back into DP2 for item identity (FR-001/FR-003, rider R2). All DP2 references are citations (FR-013); no DP2 model is re-derived. |
| II. No ERPNext fork (connector stays thin) | ✅ Pass | Every ERPNext document (Item, Customer, Warehouse, the created Sales Invoice) is addressed generically as `{doctype, name}` (FR-002, inherited from connector 004); no ERPNext field model is copied or forked. |
| III. Additive & upgrade-safe changes | ✅ Pass (N/A) | Documentation only; no schema/migration/version pin. The runtime that *will* land (poller `scheduler_event`, posting worker) ships through Gate G8 in a later slice; this plan introduces none of it. |
| **IV. Idempotent mutations** | ✅ Pass (**documented, not implemented**) | This is the spec where ERP mutation will land, so IV is first-class — but stated, not implemented. The plan records the replay key (`sourceSystem`+`externalId`, 012 O-3), the same-document-on-re-offer rule, the `409 idempotency_key_conflict` ack-replay rule, and the "no new idempotency primitive" constraint (FR-005). No mutation occurs here; Gate G5 lands on the later posting runtime. |
| V. Observable failures | ✅ Pass | Every outcome is traceable via the DP2 `request_id` correlation (spec-003 substrate) with a typed taxonomy and no secret/token/credential leak (FR-012, Gate G4/G7). The connector reuses the spec-003 / 012 taxonomy rather than inventing one. |
| **VI. Fiscal & stock truth is never hidden** | ✅ Pass (**the principle this spec most exercises**) | The typed binary terminal posting outcome IS the Principle VI enforcement: a transient ERPNext failure, a closed period, a validation failure (incl. unmapped UOM), an unmapped account, and the should-be-impossible missing-`erpnextItemRef` line each become an explicit `failed_transient` / `permanently_rejected` ack with a `reason.category` from the **closed** 012 set — never a silent partial, guess, drop, or catch-all/"Misc" Item (rider R3). DP2 sees every gap for 017 reconciliation. |
| VII. Spec-driven, contract-first delivery | ✅ Pass | This `plan.md` IS the contract-first planning gate — authored and reviewed *before* any posting code, against the signed rider + fixed 012 contract. No catalog/inventory/sales-posting/tax mutation is implemented here; the apply-only item posture and the interim/gated Payment-Entry split are recorded so implementation does not re-litigate them. |

**Apply-only vs. resolution note (Q-CON-004).** Unlike connector 004's plan (which justified
*connector-side resolution*), this plan's Principle I/II posture is **apply-only**: connector 004
FR-001/FR-003 (resolution) and the item-identity branch of its FR-006/US3 are **retired** by
`Q-CON-004` / rider R2; connector 004 FR-002 (generic addressing), FR-005 (no item-search /
no Item-creation / no auto-match source — *retained and reinforced*), and FR-008/FR-009 (UOM + money)
are **retained** and inherited here. The Constitution Check above reflects the apply-only posture, not
004's retired resolution framing.

**Result**: PASS — no violations. Complexity Tracking empty.

**Post-design re-evaluation (after Phase 1):** See [Post-Design Constitution Re-Check](#post-design-constitution-re-check).

## Project Structure

### Documentation (this feature)

```text
specs/006-sales-posting-adapter/
├── plan.md                 # This file (plan-lane artifact; hand-authored to 006's docs-only posture)
├── spec.md                 # Feature specification (planning/policy; merged PR #14) — §0/§4 untouched
├── resolution-concepts.md  # Design output: apply-only item identity, posting decision table,
│                           #   UOM/money posture, idempotency/replay, Payment-Entry gating, citations
└── follow-up-notes.md      # Design output: inherited implementation gates, planned hooks.py
                            #   scheduler_event (NOT wired), Payment-Entry gated sub-scope, forward refs
```

*No `contracts/` directory **and no `data-model.md`**: the wire contract (`posting-feed.yaml`,
`1.1.0-draft`) already exists and is **owned by DP2** — the connector cites it and authors no OpenAPI
(FR-015 / Principle I); emitting either a contract or a connector-side data model here would create a
second source of truth for the 012 entities. The "design" content the standard `/speckit-plan` Phase 1
would put in `data-model.md` / `quickstart.md` **already lives in
[resolution-concepts.md](./resolution-concepts.md)** (the `PostingWorkItem` / `SaleLine` /
`ErpnextItemRef` / `OutcomeAckRequest` entities, the decision table, and the reviewer-verification
citations in §7). This plan points at those companions rather than duplicating them — consistent with
spec.md §0's "companion documents, no `data-model.md`".*

### Source Code (repository root)

```text
(none in this slice)

retail_tower_erpnext_connector/
└── hooks.py                # UNCHANGED — stays empty at this layer (spec 001 FR-005). The posting
                            #   poller scheduler_event is a *planned* downstream task (FR-014,
                            #   follow-up-notes.md §1), NOT wired here.
```

**Structure Decision**: This is a **planning artifact only** — it adds `plan.md` under the spec folder
and changes no source. The eventual posting runtime (a `scheduler_events` poller in `hooks.py`, a
posting worker, an idempotency/dedup store, the connector-side unit→UOM map) is recorded as
*planned downstream work* in `follow-up-notes.md`; none of it is authored here. `hooks.py` is named in
this spec's lock scope to reserve it against a conflicting dispatch, but the dispatch instruction is
explicit: **no `hooks.py` edit in this lane** (follow-up-notes.md §1). No `contracts/`, no
`data-model.md`, no code, no migration.

## Complexity Tracking

> No Constitution Check violations. No complexity to justify. (Section intentionally empty.)

## Phase 0 — Outline & Research

**Status: already satisfied by the merged companion docs — no new `research.md` authored.**

The standard Phase-0 output (resolve unknowns → consolidate decisions + citations) is already
delivered by the spec's Clarifications (Session 2026-06-05, 4 Q/A resolving the resolution side,
posting model, unresolvable-line handling, and warehouse handling) and by
[resolution-concepts.md §7](./resolution-concepts.md) (the DP2 citation-verification table — every
cited DP2 path verified to locate and confirm its claim, FR-013 / `dp2-citation-verification`).

There are **no open `NEEDS CLARIFICATION` items** for this plan:

- **Resolution side** → resolved: DP2-side, apply-only (rider R2 / `Q-CON-004`).
- **First posting model** → resolved: interim submitted Sales Invoice / outstanding-AR only; SI + PE
  is the signed-but-gated target (rider R1).
- **Unresolvable / ad-hoc line** → resolved: fails-to-DLQ in DP2 before offer; no substitute Item
  (rider R2/R3/R4); an offered line lacking `erpnextItemRef` is an upstream contract violation →
  STOP-and-raise.
- **Missing warehouse mapping** → resolved: fails-to-DLQ in DP2 before offer; apply pre-resolved
  warehouse, never guess (rider R5).
- **UOM** → resolved: signed UOM decision Option A; unmapped unit → `validation` fail-closed.

**Output**: No separate `research.md`. The Phase-0 decisions + citations are
[resolution-concepts.md](./resolution-concepts.md) (esp. §1, §2, §7) and the spec's Clarifications.

## Phase 1 — Design & Contracts

**Status: design exists in the companion docs; no new `data-model.md` / `contracts/` / `quickstart.md`
authored (FR-015 / §0).**

1. **Entities** — documented in [resolution-concepts.md](./resolution-concepts.md) and spec §"Key
   Entities": `PostingWorkItem`, `SaleLine` (with required `erpnextItemRef`), `ErpnextItemRef`
   (`{doctype:"Item", name}`), the ERPNext sales document output, and `OutcomeAckRequest` /
   `RejectionReason`. **All are 012-contract entities owned by DP2** — the connector applies them; it
   defines no connector-side data model (no `data-model.md`).
2. **Interface contracts** — **none authored.** The only wire surface is the DP2-owned 012
   posting-feed (`connectorPullPostings` / `connectorAckOutcome`); the connector consumes it and emits
   no OpenAPI (FR-015, Principle I). No `contracts/` directory.
3. **Reviewer-verification ("quickstart")** — the spec's acceptance scenarios (US1–US4), the posting
   decision table ([resolution-concepts.md §3](./resolution-concepts.md)), and the citation table
   ([§7](./resolution-concepts.md)) are how a reviewer verifies the plan. No separate `quickstart.md`
   is authored; it would duplicate these.
4. **Agent context** — the repo `CLAUDE.md` "active feature" plan pointer currently targets
   `specs/004-product-erpnext-item-mapping/plan.md`. Flipping it to this 006 plan is a **deliberate,
   separate decision** (it changes the repo's declared active feature), **not** done automatically by
   this plan slice. Surface it for explicit approval before flipping.

**Output**: No new `data-model.md` / `contracts/` / `quickstart.md`. Design lives in
`resolution-concepts.md` + `follow-up-notes.md` + spec §"Key Entities".

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (design = the existing companion docs; `data-model.md` / `contracts/` /
`quickstart.md` deliberately skipped with reason — FR-015 / §0):

- **Principle I (DP2 boundary)**: Confirmed — the plan cites the fixed DP2-owned 012 contract +
  signed rider; the connector consumes the contract, authors no OpenAPI, and never reaches back into
  DP2 for item identity.
- **Principle II (no fork)**: Confirmed — every ERPNext document addressed only as `{doctype, name}`.
- **Principle IV (idempotent, documented)**: Confirmed — replay key, same-document re-offer rule, and
  ack-replay/`409` rule are stated as requirements for the later posting slice to implement; this
  plan mutates nothing and invents no idempotency primitive. Gate G5 lands on the runtime.
- **Principle V (observable)**: Confirmed — correlation via DP2 `request_id`; typed taxonomy; no
  secret leak.
- **Principle VI (truth never hidden)**: Confirmed — the binary typed terminal outcome maps every
  failure onto DP2's closed `reason.category` set; no silent partial/guess/drop/catch-all-Item path
  exists. This is the spec's load-bearing principle.
- **Principle VII (no implementation)**: Confirmed — `plan.md` is the contract-first planning gate;
  no posting/poller/idempotency-store/UOM-map code; `hooks.py` unedited (poller is a *planned*
  `scheduler_event` only). Implementation stays blocked behind the inherited DP-015 arc gates
  (follow-up-notes.md §2) and the remaining Spec-Kit chain (`tasks.md` → `execution-map.yaml`).

**Result**: PASS (post-design). No new violations. Next Spec-Kit step is `/speckit-tasks` — but it
remains **gated** behind the inherited DP-015 arc implementation prerequisites
([follow-up-notes.md §2](./follow-up-notes.md)) and is **not** authorized by this plan slice.
