# Implementation Plan: Receivables & Third-Party Posting Adapter

**Branch**: `009-receivables-and-third-party-posting-adapter` | **Date**: 2026-06-16 | **Spec**: [./spec.md](./spec.md)

**Input**: Feature specification from `specs/009-receivables-and-third-party-posting-adapter/spec.md`

**Status**: Proposed / Draft — phased approach for the OWNING repo to execute
**post-dispatch**. **No code, Frappe Python, `hooks.py` edit, OpenAPI YAML, DocType,
or SQL is authored here.** All DP-2-side artifacts (`settlement.yaml`,
`posting-feed.yaml`, and the future 012 settlement extension) are **upstream
dependencies** (spec E-1/E-2/E-4); this plan **conforms to / consumes** them. It
marks **no gate satisfied** and lifts **no rider**.

## Summary

The Connector posts an **approved** DP-2 settlement command — primarily a **cash
application** (`consoleApplyPayment`, 7-C operational truth) — to ERPNext as a
**Payment Entry** against the existing Sales Invoice that connector `006` posted,
plus claim/remittance valuation movements for a reconciled `ReconciliationResult`.
This is the slice connector `006` **deferred** (E-3). The Connector consumes DP-2
**only** over the **012 posting-feed** boundary (`connectorPullPostings` /
`connectorAckOutcome`, `connectorBearer`) — never `settlement.yaml`'s Console/POS
routes. It is idempotent (012 ack semantics) and upgrade-safe (Retail-Tower-terms
mapping, never ERPNext doctype field names). **The transport surface it consumes
does not yet exist** (the 012 `kind` enum is `[sale_post, reversal]` only —
CRITICAL-1 / OQ-1), and the Payment-Entry posting is gated behind
**011-DR-POSTING-R1** (OQ-2). Implementation is therefore **blocked** until those
two upstream items clear; this plan sequences the work *behind* them.

## Technical Context

**Language/Version**: Python 3 (Frappe app), consistent with the existing connector
(`retail_tower_erpnext_connector`). No new language introduced by this plan.

**Primary Dependencies**: The existing connector posting transport
(`connectorPullPostings` / `connectorAckOutcome`); the RATIFIED DP-2
`settlement.yaml` (G2, as the upstream fact producer — NOT an HTTP client surface
for the Connector); the **future** DP-2 012 settlement work-item extension
(CRITICAL-1, upstream, not authored here); the ERPNext Payment Entry / valuation
doctypes (addressed generically as `{doctype, name}`).

**Storage**: ERPNext (valuation projection) via the connector's existing Frappe site
binding. No new DP-2 storage. Any Connector-side config delta is a **Frappe DocType
change** (`bench migrate`), not SQL (NEEDS the 012 extension shape first).

**Testing**: Docker-free unit tests with the connector's injected-fake transport
pattern (mirroring `posting/transport.py` tests); a contract-conformance check
against the future 012 extension once it lands; bench-gated `bench migrate`
round-trip deferred as a bench-validation (connector standing-rules pattern).

**Target Platform**: Frappe/ERPNext site (the connector app), server-side.

**Project Type**: Single project — a Frappe custom app posting adapter (no
frontend/backend split).

**Performance Goals**: Inherit the 012 feed's cursor-paginated pull cadence; no new
latency target beyond connector `006` posting throughput.

**Constraints**: Idempotent (no duplicate ERPNext document on replay); upgrade-safe
(ERPNext v15→v16 is mapping-internal, 012 O-6); tax-pending (no VAT computed);
posts only **approved** commands; never edits a posted document (reversal = NEW
document via Arc A).

**Scale/Scope**: One new posting path (settlement work-item kind) layered on the
existing connector poller; bounded by the settlement work package (one parent +
five children).

## Constitution Check

*GATE: Must pass before Phase 0. Re-check after design.*

- **Principle I (DP-2 is source of truth; contract-first).** PASS — 009 authors no
  contract; it consumes the RATIFIED `settlement.yaml` (G2) and the future 012
  extension. ERPNext stays a valuation projection (NG-6).
- **Principle II (generic ERPNext addressing).** PASS — `{doctype, name}` only;
  never ERPNext field names (FR-009).
- **Principle VII (contract-first; `hooks.py` stays empty at spec layer).** PASS —
  the poller branch is a *planned* `scheduler_event`, not wired in any spec/plan
  artifact (NG-3). No `hooks.py` edit here.
- **Principle IX/X (immutable fact; no edit-in-place).** PASS — a reversal is a NEW
  document via Arc A (NG-1); 009 never edits a posted invoice / Payment Entry.
- **Architecture invariant.** PASS — Connector reaches DP-2 only via the 012
  boundary; never calls `settlement.yaml` Console/POS routes (FR-006).
- **Gate posture.** PASS for a SPECIFY/plan/tasks artifact — **no** gate marked
  satisfied; 011-DR-POSTING-R1 + the 012 extension are blocking preconditions.

No Constitution violations require justification (Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/009-receivables-and-third-party-posting-adapter/
|-- spec.md      # Proposed/Draft feature spec (authored)
|-- plan.md      # This file (phased approach; no code)
+-- tasks.md     # Contract-consuming task list (authored next; no code)
```

> No `data-model.md` / `research.md` / `contracts/` / `quickstart.md` are authored:
> like connector `006` and DP-2 `035`, this contract-consuming spec ships
> spec + plan + tasks only. The data model is **upstream** (`settlement.yaml`
> + the future 012 extension); 009 authors **no** contract or OpenAPI (NG-2/NG-3).

### Source Code (owning repo — Retail-Tower-ERP-Next-Connector; POST-dispatch only)

```text
retail_tower_erpnext_connector/
+-- posting/                 # existing posting transport + sale-post adapter (006)
    +-- (planned, post-dispatch) settlement posting path: a poller branch for the
        new 012 settlement work-item kind + a Payment-Entry / valuation mapping
        module (Retail-Tower terms -> ERPNext {doctype, name}). NOT authored here.
```

**Structure Decision**: Single Frappe-app project. The settlement posting path is an
**additive branch** on the existing connector poller/transport (the same surface
006 uses), not a new service. No structural change is made by this artifact; the
tree above is the *planned* post-dispatch layout.

## Phase 0 — Upstream preconditions (NO code; hard blockers)

- **[OQ-1 / CRITICAL-1] 012 settlement work-item extension exists.** Confirm DP-2 has
  authored & ratified the **versioned, backward-compatible 012 extension** carrying
  the approved settlement / cash-application / claim / remittance command (a new
  `PostingWorkItem.kind`, + `erpnextPaymentEntryRef` / tender fields). Today the 012
  `kind` enum is `[sale_post, reversal]` only (spec E-4). **Hard blocker** — there
  is nothing to pull until this lands. 009 authors **none** of it.
- **[OQ-2 / 011-DR-POSTING-R1] Posting-authorization rider lifted for Payment Entry.**
  Confirm the owner has lifted 011-DR-POSTING-R1 for the Payment-Entry posting (DP-2
  035 §OQ-7). **Hard blocker** on FR-001.
- **[G2] Contract re-read at dispatch.** Re-read DP-2 `origin/main`: confirm
  `settlement.yaml` (G2) and the 012 extension still match the spec's Evidence basis;
  snapshot, not live view.
- **[G10] Connector boundary verified.** Confirm 028 boundary decisions are signed
  and G10 is verified for this `connector`-scoped consumer (spec §8).

## Phase 1 — Settlement posting path (FR-001/FR-002/FR-003) — [consumes 012 extension]

**Goal:** post an approved cash application as one ERPNext **Payment Entry** against
the existing Sales Invoice, acking the document ref (feeding `erpnextPaymentEntryRef`).

- Add a **poller branch** for the new 012 settlement work-item kind (alongside the
  existing `sale_post` / `reversal` branches) — applies the pre-resolved references,
  resolves nothing (FR-010, NG-8).
- Author a **Payment-Entry mapping module** translating the approved cash-application
  command (Retail-Tower terms) into an ERPNext Payment Entry addressed `{doctype,
  name}` (FR-009), applied against the existing invoice — **no re-post** (NG-5).
- Ack the outcome via `connectorAckOutcome` with the ERPNext document ref (FR-002);
  rely on the 012 ack idempotency — replay never double-posts (FR-007).
- **Test strategy:** Docker-free unit tests (injected-fake transport): full clearing
  payment → one Payment Entry; partial → partial Payment Entry; replay → no
  duplicate; permanent ERPNext rejection → `permanently_rejected` with structured
  reason. A contract-conformance check against the 012 extension shape.

## Phase 2 — Claim / remittance valuation posting (FR-004) — [consumes 012 extension]

**Goal:** post the ERPNext valuation movement for a reconciled `ReconciliationResult`.

- Extend the settlement poller branch to handle the claim/remittance reconciliation
  command (`settled | partial | flagged`), posting the matching ERPNext valuation
  document(s) against the claimed receivable(s) (FR-004).
- **[OQ-3]** Decide the exact ERPNext document for a claim/remittance valuation
  (Payment Entry vs Journal Entry vs credit/debit note) — a plan/design mapping
  decision; framed conceptually here, resolved at design time.
- **Test strategy:** unit tests for settled (clears), partial (records variance),
  flagged (deterministic safe outcome) — mirroring Phase 1's fake-transport pattern.

## Phase 3 — Reversal routing via Arc A (FR-005) — [reuse; no new model]

**Goal:** ensure a rejected claim line / reversal reuses **Connector Arc A**.

- **No new posting kind.** Confirm the rejection/reversal path routes to the existing
  Arc A forward-feed reversal (the 012 `kind: reversal` work-item) + DP-026 + POS-014
  (NG-1, FR-005). 009 builds nothing parallel.
- **[OQ-4]** Document how a receivable 009 posted a Payment Entry for **consumes** a
  later DP-026 reversal (the §OQ-4 CARVE; reversal-compatibility fields are deferred
  upstream until DP-026 closes) — Arc A reuse only.
- **Test strategy:** a routing assertion that a rejected line produces an Arc A
  reversing document and **no** 009-specific reversal kind.

## Phase 4 — Idempotency, audit, observability, tax-pending (FR-007/011/012/013/014)

- Verify idempotency via the 012 ack semantics across all settlement kinds (FR-007).
- Wire posting-attempt audit (work-item ref, ERPNext document ref, outcome, time)
  and posting-health observability, consistent with connector `006` + 012 (FR-013);
  secrets never logged (G4).
- Confirm tax-pending posting — placeholder carried verbatim, no VAT computed
  (FR-011, NG-4) — and tenant/store scoping via `connectorBearer` (FR-014).

## Phase 5 — Documentation closeout (owning-repo docs; no gate)

- Record (in the connector's own decision/runbook docs, post-dispatch) that the
  deferred-from-006 Payment Entry now posts, keyed to the 012 settlement extension,
  and the 006↔009 carve. **Owning-repo docs, authored post-dispatch, not here.**

## Gate tag summary

| Phase | Gate tags | Note |
|-------|-----------|------|
| 0 Preconditions | OQ-1 (012 ext), OQ-2 (011-DR-POSTING-R1), G2, G10 | All hard blockers; NONE satisfied here. |
| 1 Payment Entry | G2 (consume), 011-DR-POSTING-R1 (gated) | The deferred-from-006 core (FR-001). |
| 2 Claim/remittance valuation | G2 (consume) | OQ-3 mapping decision at design. |
| 3 Reversal routing | — | Arc A reuse only (NG-1); no new model. |
| 4 Idempotency/audit/tax | G4 (adjacent) | Conform to 003 secret discipline + 012 idempotency. |
| 5 Docs closeout | — | Owning-repo docs only. |

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |

## Out of scope (re-stated)

- No DP-2 file / contract / migration edit — `settlement.yaml`, `posting-feed.yaml`,
  and the future 012 extension are upstream (NG-2).
- No re-post of the Sales Invoice — 006 owns it (NG-5).
- No competing reversal model — Arc A + DP-026 + POS-014 reuse (NG-1).
- No item/warehouse/account resolution — apply pre-resolved refs only (NG-8).
- No VAT/tax allocation — tax-pending (NG-4).
- No new credential/auth scheme — `connectorBearer` boundary reuse (NG-7).
- No gate marked satisfied; 011-DR-POSTING-R1 not lifted.

---

> **SPECIFY/plan/tasks record (Proposed / Draft).** This plan describes a
> post-dispatch approach for the owning repo; it authors no code, contract, or
> migration. Dispatch requires explicit scoped owner approval after the Phase 0
> upstream preconditions (012 extension + 011-DR-POSTING-R1) clear and G10 is
> verified.
