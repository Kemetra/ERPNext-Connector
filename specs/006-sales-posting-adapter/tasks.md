<!--
  /speckit-tasks output for connector 006 Sales Posting Adapter.
  PLANNING-ONLY artifact: this is the ordered task list. It authorizes NO implementation and NO dispatch.
  [GATED] tasks touch a forbidden surface (standing-rules §3) and require explicit per-slice approval before they run.
  [SIGN-OFF] tasks are owner decisions recorded before dependents run.
  ⏳ BENCH-VALIDATION tasks are validated on a staging ERPNext v15 site (no local bench; standing-rules §6) — authored now, run later.
  Authoring this file (and a future execution-map.yaml) does NOT authorize the first implementation slice — the first slice
  touching retail_tower_erpnext_connector/** runtime code (poller, posting worker, idempotency store) is a threshold the user crosses explicitly.

  Lane note (spec.md §0 / follow-up-notes.md §4): those merged artifacts list "no plan.md, tasks.md" — that describes the
  spec-authoring lane (PR #14), NOT a permanent exclusion (spec.md §0 itself names "the connector's own Spec-Kit chain
  plan.md → … → tasks.md → execution-map.yaml"). This is the deferred tasks-lane slice; the merged §0/§4 stay verbatim.
-->

# Tasks: Sales Posting Adapter (connector consume/post side)

**Feature**: 006-sales-posting-adapter | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Design**: [resolution-concepts.md](./resolution-concepts.md) (apply-only posture, decision table, UOM/money) · [follow-up-notes.md](./follow-up-notes.md) (inherited gates, planned `hooks.py` poller, Payment-Entry sub-scope)
**Fixed contract (read-only input, DP2-owned)**: `Data-Pulse-2/packages/contracts/openapi/erpnext-connector/posting-feed.yaml` (`1.1.0-draft`)

---

## 0. TL;DR — the connector side of the fixed 012 posting feed, in the interim SI-only mode

006 turns a Data-Pulse-2 **posting work-item** (a validated 008 sale projection) into ERPNext accounting truth by **consuming the fixed 012 pull/feed contract**: the connector PULLs pending work-items (`connectorPullPostings`), creates one submitted ERPNext **Sales Invoice** per sale (interim mode), and ACKs a typed outcome (`connectorAckOutcome`). The connector is the **only ERPNext-calling component** and **authenticates *to* DP2** (client; DP2 makes no outbound calls — spec 003 / Gate G4). Item identity is **applied, never resolved**: each offered line carries a DP2-pre-resolved `erpnextItemRef` (`{doctype:"Item", name}`); the connector applies it and performs **no** resolution/lookup/reach-back/cache (rider R2 / `Q-CON-004`). The reconciliation run + DLQ drain + repair is **DP2-side (017)** — the connector only emits typed outcomes.

**Ratified decisions inherited (owner rider `011-DR-POSTING-R1`, 2026-06-05):**
- **R1** — first slice posts a **submitted Sales Invoice only** (outstanding AR); **gated**, **not finance-complete**. Payment Entry is a later, separately-gated arc.
- **R2** — **DP2 resolves** line→Item at projection; the connector applies `erpnextItemRef` and never guesses. (Connector 004 FR-001/FR-003 retired.)
- **R3** — disabled/non-sales Item → DP2 fails-to-DLQ before offer; **no substitute / "Misc" item** in the connector.
- **R4** — unknown-items ≠ unmapped-for-posting; an ad-hoc line still needs a confirmed 013 mapping before it can post.
- **R5** — no resolved warehouse → DP2 fails-to-DLQ (`unmapped_store`); the connector applies the pre-resolved warehouse, never guesses.

**Authoring-gate prerequisites satisfied on DP2 `main` (verified 2026-06-06):** `P-DP-008-LIVELOOP` (DP-2 #496/#497), 014-CRUD warehouse map (#495), 012 `erpnextItemRef` (#494), DP-015 Spec-Kit chain (#500). `follow-up-notes.md §2` (merged §3-gated) recorded these as owner-deferred on 2026-06-05; this dated note reconciles it — that file is left untouched.

> **Authoring ≠ dispatch.** This list is authored because the *authoring* gate is open. The first **implementation** slice additionally depends on the inherited **execution** dependencies (§11): DP2 actually serving the live posting feed end-to-end, and a staging ERPNext v15 bench. No task here is self-authorized.

## 1. Conventions

- **Checklist format**: `- [ ] [TaskID] [P?] [Story?] Description (file path).`
- **Labels**: `[P]` parallelizable (different files, no incomplete-task dependency); `[GATED]` touches a forbidden surface (standing-rules §3 — `hooks.py`, DocType JSON, `pyproject.toml`, `patches.txt`) → explicit per-slice approval before it runs; `[SIGN-OFF]` an owner decision recorded before dependents run; **`⏳ BENCH-VALIDATION`** validated on a staging ERPNext v15 site, not locally (standing-rules §6).
- **TDD where locally runnable**: pure-Python tasks (UOM map, the work-item→invoice builder, the reason-category mapper) get RED→GREEN locally (≥80% coverage, Python rules). Tasks asserting against a *live installed app* (posting submit, idempotent replay, scheduler) are `⏳ BENCH-VALIDATION` — authored now, run on the bench (spec 001's convention).
- **Predecessor semantics**: "Predecessors: T0XX" means T0XX is **ordered before** this task. For a `[GATED]` / deferred predecessor (e.g. T093, the poller), it means that task is **authored-as-deferred / sequenced**, *not* that its forbidden-surface edit has been executed — a dependent task (e.g. T092 closeout) is satisfied by the gated task being correctly recorded as deferred, never by crossing its gate in this lane.
- **Auth (CONTRACT)**: the posting feed/ack is a **machine** surface → the connector uses the spec-003 service-auth model (`connectorBearer`-class, opaque-revocable, tenant-scoped) to authenticate **to** DP2. No new auth primitive.
- **Money**: exact-decimal string + ISO-4217, no float (Principle VI / FR-009); DP2 amounts authoritative.
- **The 012 `posting-feed.yaml` is a READ-ONLY input** — the connector authors/edits no OpenAPI (FR-015, Principle I).
- **`hooks.py` stays empty in this lane** (spec 001 FR-005). The poller is a *planned* `scheduler_event` (FR-014) — recorded, `[GATED]`, **not wired**.

## 2. Approval-gated (`[GATED]`) and decision-gated (`[SIGN-OFF]`) tasks

| Task | Type | Gate |
|---|---|---|
| T001 | `[SIGN-OFF]` | Confirm the **apply-only item posture** (rider R2 / `Q-CON-004`): the connector applies `erpnextItemRef`, performs NO resolution/lookup/reach-back/cache; connector 004 FR-001/FR-003 retired, FR-002/FR-005/FR-008/FR-009 retained. Must be recorded before any posting-worker task. |
| T002 | `[SIGN-OFF]` | Confirm the **interim SI-only mode** (rider R1): the first slice posts a submitted Sales Invoice only (outstanding AR), **gated** + **not finance-complete**; no Payment Entry / tender state or payload. Deriving a PE from `posTotal` is STOP-and-raise. |
| T003 | `[SIGN-OFF]` | Confirm the connector emits **typed outcomes only**; the reconciliation run + DLQ drain + repair is **DP2-side (017)**, not built here. |
| T020 | `[GATED]` | The **idempotency store** for `(sourceSystem, externalId) → documentRef`. If realized as a Frappe **DocType**, its `*/doctype/**/*.json` is a forbidden surface (standing-rules §3) → explicit approval + its own slice + rollback note (Principle III). |
| T093 | `[GATED]` | Register the posting **poller** as a `scheduler_events` entry in `retail_tower_erpnext_connector/hooks.py` (FR-014). `hooks.py` is a forbidden surface AND follow-up §1 says **not wired in this lane** → a separate, later, approved implementation slice. **Recorded here to sequence it, NOT to execute it.** |

> **No 012 contract task.** The connector consumes the **fixed** DP2-owned `posting-feed.yaml`; the rider-R2 `erpnextItemRef` correction is already on DP2 `main` (#494). Any further contract change (payment/tender extension) is a DP2-side `[GATED]` 012 slice — out of connector 006 (FR-015).
> **No item-resolution task.** Deliberately absent (rider R2 / retired FR-001/FR-003). A "resolve `tenantProductRef`" task would reintroduce the superseded posture — it must never appear.

## 3. User scenarios → task mapping

| Story | Scope (from spec.md) | Tasks |
|---|---|---|
| US1 (P1) 🎯 MVP | **Post a validated work-item** as one submitted ERPNext Sales Invoice, **applying** each line's `erpnextItemRef`, addressing every doc generically `{doctype, name}`, ack `posted` + `documentRef` | T030–T034 |
| US2 (P1, co-equal) | **Idempotent, retry-safe posting**: key on `sourceSystem`+`externalId` (O-3); re-offer echoes the same `documentRef`; ack-replay deterministic / `409` on conflict; no new idempotency primitive | T040–T042 |
| US3 (P1, co-equal) | **Classify & surface failures**: `failed_transient` XOR `permanently_rejected` (closed `RejectionReason.category` set); no partial/guess/drop; sale fact never mutated; `STOP-and-raise` on a missing `erpnextItemRef` (upstream contract violation) | T050–T052 |
| US4 (P2) | **Reconcile UOM, money, warehouse** per signed decisions: unit→UOM (Option A, unmapped→`validation`); exact-decimal+ISO-4217 money; apply pre-resolved warehouse (never guess) | T070–T072 |
| (NOT 006) | **DLQ drain + reconciliation run + repair** | — DP2-side **017** (§11) |
| (later, gated) | **Payment Entry posting** | — separate arc, rider R1 (§11) |
| (polish) | observability (Principle V / G7), coverage, closeout | T090–T093 |
| (traceability) | **DP2-citation integrity** (FR-013 / SC-002): every DP2 path resolves + confirms its claim | verified in [resolution-concepts.md §7](./resolution-concepts.md) (companion doc, no build task); re-checked at closeout (T092) |

---

## 4. Phase 1 — Setup & sign-offs

- [ ] T001 [SIGN-OFF] Record the **apply-only item posture** decision (rider R2 / `Q-CON-004`) in a future `wave-status.md` / the spec's Clarifications trace. Predecessors: none. Acceptance: recorded; the retired-vs-retained table ([resolution-concepts.md §1](./resolution-concepts.md)) referenced; no resolution/lookup/cache task exists anywhere in this list.
- [ ] T002 [SIGN-OFF] Confirm the **interim SI-only mode** (rider R1): no Payment Entry / tender state or payload in 006's first slice; PE is a later separately-gated arc; deriving a PE from `posTotal` is STOP-and-raise. Predecessors: T001. Acceptance: recorded; no tender/payment field in any 006 allowed-files set.
- [ ] T003 [SIGN-OFF] Confirm the connector produces **typed outcomes only**; the reconciliation run + DLQ drain + repair is **DP2-side (017)**. Predecessors: T002. Acceptance: recorded; no scheduled reconciliation/repair job in any 006 allowed-files set.
- [ ] T004 [P] Scaffold the posting module skeleton `retail_tower_erpnext_connector/connector/posting/` (empty `__init__.py`, `posting_worker.py`, `posting_client.py` stubs — no logic), mirroring the spec-001 module layout. Predecessors: T003. Acceptance: package imports clean (`python -m py_compile`); registered in no hook yet; existing modules unaffected.

## 5. Phase 2 — Foundational (block all capability slices)

### 5.1 The 012 work-item client (read-only consume of the fixed contract)

- [ ] T010 [P] Author `posting_client.py`: typed read-models for `PostingWorkItem` / `SaleLine` (with required `erpnextItemRef`) / `OutcomeAckRequest` / `RejectionReason`, mapped 1:1 from the fixed 012 `posting-feed.yaml` — `@dataclass(frozen=True)` DTOs (Python rules), no field invented, no DP2 model re-derived (FR-013/FR-015). Predecessors: T004. Acceptance: `py_compile` + a local unit test asserting each DTO mirrors the 012 schema fields; coverage ≥80% on the module.
- [ ] T011 [P] Author the **pull/ack transport** in `posting_client.py`: `connectorPullPostings` (cursor-paged GET) + `connectorAckOutcome` (POST) over the spec-003 `connectorBearer`-class auth to DP2, carrying the DP2 `request_id` correlation; no outbound mutation of DP2 (Principle I). Predecessors: T010. Acceptance: local unit test with a mocked DP2 HTTP surface (no live DP2); correlation id propagated; ⏳ BENCH-VALIDATION for the live two-op round-trip.

### 5.2 The idempotency store (`[GATED]` if a DocType)

- [ ] T020 [GATED] Request explicit approval, then realize the **idempotency store** keyed on `(sourceSystem, externalId) → documentRef` (O-3 anchor). If a Frappe DocType: its `*/doctype/**/*.json` is forbidden-surface (standing-rules §3) → its own slice, additive migration + rollback note (Principle III). The store records the posted ERPNext `documentRef` so a re-offer echoes it unchanged (FR-005). Predecessors: T010, T001. Acceptance: ⏳ BENCH-VALIDATION — a second offer of the same `(sourceSystem, externalId)` resolves to the existing `documentRef` and creates no second document; lock/migration reviewed (G3).

## 6. Phase 3 — US1 (P1) 🎯 MVP: post a validated work-item → submitted Sales Invoice

- [ ] T030 [P] [US1] Author the **work-item → Sales Invoice builder** (`posting_worker.py`): map header provenance (`sourceSystem`+`externalId`) + each line **applying** its `erpnextItemRef` as `{doctype:"Item", name}` (FR-001/FR-002), money as exact-decimal+ISO-4217 (FR-009). Pure transform, no ERPNext call. Predecessors: T010. Acceptance: local RED→GREEN — a fixture work-item produces the expected invoice payload; **no** resolution/lookup step appears; coverage ≥80%.
- [ ] T031 [US1] ⏳ BENCH-VALIDATION — `posting_worker.py` **submits** the built invoice on ERPNext (one submitted Sales Invoice per sale, interim SI-only), addressing the created doc generically `{doctype, name}`. Predecessors: T030, T020. Acceptance: on staging, a resolved-line work-item yields one submitted Sales Invoice; `documentRef` captured.
- [ ] T032 [US1] ⏳ BENCH-VALIDATION — the success ack: on submit, `posting_worker.py` ACKs `posted` + `documentRef` over `connectorAckOutcome`; the DP2 sale fact is not mutated. Predecessors: T031, T011. Acceptance: on staging, DP2 records `posted` with the connector's `documentRef`.
- [ ] T033 [P] [US1] Money + temporal fidelity in the builder: exact-decimal string money verbatim from the 012 work-item, no float; `businessDate`→ERPNext `posting_date`. Predecessors: T030. Acceptance: local test — a delayed sale builds its original `businessDate`; no float anywhere.
- [ ] T034 [P] [US1] **Missing-`erpnextItemRef` guard** (upstream contract violation per R2): an offered line lacking `erpnextItemRef` → fail-closed `permanently_rejected` / `validation` + **STOP-and-raise**; never substitute a "Misc" item (R3). Predecessors: T030. Acceptance: local test — such a line never builds a partial invoice; raises + maps to the correct outcome.

## 7. Phase 4 — US2 (P1, co-equal): idempotent, retry-safe posting

- [ ] T040 [P] [US2] Author the **replay key** logic: every post resolves `(sourceSystem, externalId)` against the T020 store before building/submitting; an already-posted key short-circuits to the recorded `documentRef` (FR-005, O-3). Predecessors: T020, T030. Acceptance: local test — a duplicate key returns the existing `documentRef`, builder/submit not re-entered.
- [ ] T041 [US2] ⏳ BENCH-VALIDATION — duplicate-`posted` echo: a DP2 re-offer of an already-posted `(sourceSystem, externalId)` ACKs the SAME `documentRef` and creates no second ERPNext document (Principle IV / Gate G5). Predecessors: T040, T031. Acceptance: on staging, exactly one document survives N re-offers.
- [ ] T042 [P] [US2] Ack-replay semantics (reuse the 012 `Idempotency-Key`): the same key + same logical outcome replays deterministically; a different outcome for the same key surfaces `409 idempotency_key_conflict`; no new idempotency primitive invented. Predecessors: T011, T040. Acceptance: local test against the mocked ack surface; ⏳ BENCH-VALIDATION for the live `409`.

## 8. Phase 5 — US3 (P1, co-equal): classify & surface failures (never silently)

- [ ] T050 [P] [US3] Author the **reason-category mapper**: map each connector-internal failure to exactly one 012 `RejectionReason.category` from the **closed** set (`validation | closed_period | unmapped_item | unmapped_account | other`) per the decision table ([resolution-concepts.md §3](./resolution-concepts.md)); **no new wire reason invented**. Predecessors: T010. Acceptance: local RED→GREEN — every table row 1–9 maps to the documented category; an unmapped internal reason raises rather than inventing a code; coverage ≥80%.
- [ ] T051 [US3] ⏳ BENCH-VALIDATION — transient vs permanent on ERPNext: a transient failure (timeout/lock) → ACK `failed_transient` (DP2 re-offers; **no connector self-retry loop**); a non-retryable failure (closed period, validation, unmapped account) → ACK `permanently_rejected` + the mapped category; **nothing posted**. Predecessors: T050, T031. Acceptance: on staging, each failure lands in exactly one typed outcome; no partial document.
- [ ] T052 [P] [US3] Failure invariants (local-assertable): no failure path mutates the DP2 sale fact; no partial/guess/drop branch exists; no secret/token/credential/ERPNext-internal leaks into the outcome message (Principle V / Gate G4). Predecessors: T050. Acceptance: local test — the failure path emits only the typed outcome + category + correlation id; a leak-scan asserts no secret in the payload.

## 9. Phase 6 — US4 (P2): reconcile UOM, money, warehouse per signed decisions

- [ ] T070 [P] [US4] Author the **unit→ERPNext-UOM map** (signed UOM decision, Option A — `docs/decisions/mapping-uom.md`): a connector-side map; an **unmapped** unit fails closed as `permanently_rejected` / `validation` (row 5), never a silent default (Principle VI). Predecessors: T030, T050. Acceptance: local RED→GREEN — a mapped unit resolves; an unmapped unit raises → the `validation` outcome; coverage ≥80%.
- [ ] T071 [P] [US4] **Warehouse application** (rider R5): the builder applies the DP2-pre-resolved store/warehouse identity generically `{doctype, name}`; it never derives/guesses a warehouse; a missing-warehouse offered work-item is treated as an upstream violation (should have DLQ'd in DP2). Predecessors: T030. Acceptance: local test — the resolved warehouse is applied verbatim; no warehouse-derivation branch exists.
- [ ] T072 [P] [US4] Money representation **conformance assertion** (NOT a re-implementation of T033 — it asserts the T033 builder's output across the full header + every line): every monetary field is exact-decimal string + ISO-4217 `CurrencyCode`, matching the 012 `DecimalAmount`/`CurrencyCode` shapes. Predecessors: T033. Acceptance: a conformance test over the built invoice asserts no float and a present currency code on header + all lines; introduces no second money-building path.

## 10. Phase 7 — Polish

- [ ] T090 [P] Observability (Principle V / Gate G7): the poller + worker emit structured logs + the Principle-V signals (pull lag, failed-ack rate, permanent-rejection rate) carrying the DP2 `request_id` correlation + tenant context; raw payloads / secrets never logged. Predecessors: T032, T051. Acceptance: signals registered in a shared metrics module (not per-feature); a log-scan asserts no secret/PII; ⏳ BENCH-VALIDATION for the live signal emission.
- [ ] T091 [P] Coverage ≥80% on the new `posting/` module's locally-runnable units (client DTOs, builder, reason-mapper, UOM map); the bench-coupled paths are exercised on staging, not counted in local coverage. Predecessors: T090. Acceptance: `pytest --cov` ≥80% on the pure-Python surface.
- [ ] T092 [GATED] The poller registration (T093) + closeout: author `execution-map.yaml` + `wave-status.md` for 006 (terminal state of this planning chain). Predecessors: T091, T093. Acceptance: map/wave-status authored; the poller task remains `[GATED]`/deferred; no `hooks.py` edit performed.
- [ ] T093 [GATED] Register the posting poller as a `scheduler_events` entry in `retail_tower_erpnext_connector/hooks.py` (FR-014) that PULLs (`connectorPullPostings`), invokes `posting_worker.py` per work-item, and ACKs (`connectorAckOutcome`). **NOT wired in this lane** (follow-up §1) — a separate, later, explicitly-approved implementation slice; ships through Gate G8 (staging upgrade). Listed at end-of-sequence deliberately: it depends on the full runtime (T011/T031/T041/T051) existing + bench-validating first. Acceptance: ⏳ BENCH-VALIDATION on staging — the scheduled job pulls/posts/acks end-to-end; **only authored when its forbidden-surface gate is explicitly opened.**

---

## 11. Inherited execution dependencies & later arcs (NOT 006 implementation slices)

- [ ] T100 [DEP — DP2] **Live posting feed served end-to-end**: connector *execution* (not authoring) depends on DP2 actually offering processed work-items over `connectorPullPostings` (the DP-015 implementation, gated on its own dispatch — DP2 015 tasks T010/T012/T030+). DP2 015's planning chain is on `main` (#500); its implementation is separately gated. Traceability only.
- [ ] T101 [DEP — bench] **Staging ERPNext v15 bench**: every `⏳ BENCH-VALIDATION` task above runs here; not locally runnable (standing-rules §6). Connector Gates G5 (idempotency) / G7 (observability) / G8 (upgrade) / G9 (pilot) land on this runtime. Traceability only.
- [ ] T102 [PROPOSED — DP2 017] **DLQ drain + reconciliation run + repair**: consumes the connector's `permanently_rejected` outcomes + reconciliation flags; the repair re-post must resolve to the same `documentRef` (idempotency holds across repair). DP2-side; not a connector slice. Traceability only.
- [ ] T103 [PROPOSED — later, separately gated] **Payment Entry posting** (completing the signed SI+PE target, rider R1): requires a DP2 tender/payment fact model → a `[GATED]` 012 payment extension → connector idempotent PE creation → payment repair semantics. STOP-and-raise if attempted before these land. Traceability only.

---

## 12. Findings (carried into a future execution map)

- **Apply-only is structural, not incidental** — there is deliberately **no** item-resolution task (rider R2 / `Q-CON-004` retired connector 004 FR-001/FR-003). Any future "resolve `tenantProductRef`" task reintroduces the superseded posture and must be rejected. T001 records this; T034 guards the missing-`erpnextItemRef` upstream-violation case.
- **Bench split** — pure-Python tasks (T010, T030, T033, T034, T040, T042, T050, T052, T070, T071, T072) are locally RED→GREEN; the live posting/idempotency/observability tasks are `⏳ BENCH-VALIDATION` (T031, T032, T041, T051, T090, T093) — authored now, validated on staging (standing-rules §6); **mixed-mode** tasks have both a local unit (mocked) and a `⏳ BENCH-VALIDATION` live component (T011 — local mock + live two-op round-trip; T020 — local store logic + live no-duplicate proof). Local coverage (T091) counts only the pure-Python surface (incl. the local components of the mixed-mode tasks).
- **Gate timing** — the *authoring* gate is open (DP2 prereqs satisfied on `main`, verified 2026-06-06: #494/#495/#496/#497/#500). The *dispatch* gate is not: the first runtime slice is an explicit threshold (§0), and execution waits on T100/T101. `follow-up-notes.md §2` (merged, §3-gated) is stale-but-untouched; this file's dated notes reconcile it.
- **Forbidden surfaces sequenced, not crossed** — T020 (idempotency-store DocType JSON) and T093 (poller in `hooks.py`) are `[GATED]`; they appear to *order* the work, explicitly not to execute it in this lane.
