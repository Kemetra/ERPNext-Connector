# Feature Specification: Receivables & Third-Party Posting Adapter

**Feature Branch**: `009-receivables-and-third-party-posting-adapter`

**Feature ID**: 009

**Short name**: receivables-and-third-party-posting-adapter

**Created**: 2026-06-16

**Status**: Proposed / Draft (SPECIFY + clarify + plan + tasks). This document
produces **no** connector code, no `hooks.py` edit, no OpenAPI YAML, no Frappe
DocType, no migration, no package/lock, and no CI. It defines the **target
posting model** by which the Connector translates **approved** Data-Pulse-2
settlement / receivable / claim posting commands into ERPNext accounting
documents, and the **gates that must clear before any of it is built**. It marks
**no gate satisfied**.

> **Numbering note.** Number `009` is **owner-directed** (the `X-2` allocation for
> the settlement work package; see DP-2 035 §12). Connector specs `005` and `008`
> are **intentional gaps** in this repo's sequence — do **NOT** backfill them.
> The highest existing connector spec at specify time is
> `specs/007-connector-admin-counterpart/`; `009` skips `008` by owner direction,
> not by collision. No existing artifact is reused, renamed, or overwritten.

**Input**: Owner / program dispatch — the settlement work package opened by
**DP-2 035 (sale-settlement-and-receivables-model)**. DP-2 035 is the parent
producer; its **G2 contract** `settlement/settlement.yaml` is the contract of
record the five children consume. This feature is the **Connector child
(009)**: the later consumer that posts approved settlement / receivable / claim
financial movements to ERPNext (FR-018 of DP-2 035). It authors no DP-2 file,
no contract, no migration, and no competing reversal model.

---

## 0. What this spec IS and IS NOT (read first)

This is a **contract-consuming planning / policy spec** for the Connector child of
the settlement work package — the same SPECIFY/plan/tasks posture as connector
`006` (sales-posting-adapter) and DP-2 `035` (parent producer). It exists to:

- **Define** how the Connector turns an **approved** DP-2 settlement / receivable /
  cash-application / claim / remittance posting command into an ERPNext accounting
  document (invoice / **Payment Entry** / credit note), at product-contract level.
- **Carve** the Connector's role cleanly against connector `006` (which already
  owns the submitted **Sales Invoice** posting and **deferred** the Payment Entry)
  and against DP-2 035 (which owns every settlement *decision*).
- **Identify** the gates and the missing transport surface that MUST clear before
  any posting code is written.

This spec **MUST NOT**:

- Author or edit any OpenAPI YAML — `settlement/settlement.yaml` (DP-2 035 G2),
  `erpnext-connector/posting-feed.yaml` (DP-2 012), and any DP-2 contract are
  **upstream dependencies**; this spec **conforms to / consumes** them, it does not
  author or modify them.
- Author or edit any Frappe / connector application code, `hooks.py`,
  poller, posting worker, DocType, DB schema, migration, package/lock, CI, secret,
  or env file.
- Author any **DP-2** file or any **sibling-repo** spec.
- Define a **competing** reversal / void / refund / insurance-rejection workflow —
  those **reuse Connector Arc A** (forward-feed reversal posting) + DP-026 +
  POS-014 (NG-1; no parallel reversal model).
- Invent Egypt-VAT allocation rules (tax is activation-only under ADR-0003; the
  Connector posts whatever the upstream command carries, computing no VAT — NG-4).
- Mark **any** gate satisfied. The Connector posting is gated behind
  **011-DR-POSTING-R1** (DP-2 035 §OQ-7), and the settlement transport surface the
  Connector would consume does **not yet exist** on the 012 posting-feed (§ E-4,
  CRITICAL-1). This spec frames intent; it certifies no gate (§13).

### 0.1 Where 009 sits in the settlement work package

```
        DP-2 035  sale-settlement-and-receivables-model   (parent producer)
        '-- authors G2 contract  settlement/settlement.yaml  (RATIFIED, PR #574)
                  |  unblocks children
                  v
   POS 020        Console 017 / 018 / 019        +- Connector 009 (THIS SPEC) ----+
   capture intent  payer accounts / receivables   | posts APPROVED settlement     |
                   / claims / reconciliation       | commands to ERPNext           |
                                                    | (invoice / Payment Entry /    |
                                                    |  credit note); LATER          |
                                                    |  consumer (FR-018)            |
                                                    +-------------------------------+
```

Architecture invariant (non-negotiable; CLAUDE.md, DP-2 035 §0):

```
POS-Pulse  ->  Data-Pulse-2  ->  Retail-Tower-ERP-Next-Connector  ->  ERPNext/Frappe
```

The Connector reaches DP-2 **only via the DP-012 posting-feed boundary**
(`connectorPullPostings` / `connectorAckOutcome`), as connector `006` established.
It **never** calls `settlement.yaml`'s Console (`cookieAuth`) or POS
(`operatorAuthorization`) routes — those are **not** the Connector's HTTP surface.
The Connector is **never** in the POS capture or auth path. ERPNext stays
valuation / back-office; DP-2 stays the source of truth (Constitution §I/§III/§IX).

---

## Clarifications

### Session 2026-06-16

- Q: Does the Connector call `settlement.yaml`'s `consoleApplyPayment` /
  `consoleSubmitClaim` / `posRecordSettlementIntent` directly to learn what to
  post? → A: **No — it consumes APPROVED posting commands over the DP-012
  posting-feed boundary** (`connectorPullPostings` pull + `connectorAckOutcome`),
  exactly as connector `006` does for sale posts. The `settlement.yaml`
  operationIds are the **upstream source / contract-of-record** that *produce* the
  receivable / cash-application / claim / remittance facts; DP-2 projects an
  **approved** posting work-item onto the feed, and the Connector posts it.
  *(Rationale: architecture invariant — the Connector is a machine principal with a
  `connector`-scoped bearer, not a `cookieAuth` human session nor an
  `operatorAuthorization` POS envelope; it cannot and must not call the management
  surface. Non-critical: the invariant + 006 precedent already govern this.)*
- Q: Does 009 post the **Sales Invoice**, double-posting what connector `006`
  already owns? → A: **No — 006 owns the submitted Sales Invoice (forward AR); 009
  adds the Payment Entry / cash-application valuation against that existing
  invoice, plus claim/remittance valuation postings.** 006 explicitly **deferred**
  the Payment Entry ("first slice is submitted Sales Invoice / outstanding-AR only;
  Payment Entry deferred and gated"). 009 is the slice that lands the deferred
  Payment-Entry posting, keyed to `Receivable.erpnextPaymentEntryRef`.
  *(Rationale: 006 §0/§Clarifications + DP-2 035 §OQ-7 "7-C"; non-critical, a
  carve-of-responsibility default.)*
- Q: How does 009 handle a void / refund / insurance-rejection that would settle a
  receivable negatively? → A: **It reuses Connector Arc A** (forward-feed reversal
  posting — a NEW reversing credit note / return invoice, never an edit) together
  with DP-026 + POS-014. 009 builds **no parallel reversal model** (NG-1). The
  forward invoice + Payment Entry are 009's; reversal credit notes are Arc A's.
  *(Rationale: DP-2 035 NG-1 + 035-DR-SETTLEMENT §OQ-4 CARVE + the 012 feed's
  existing `kind: reversal` work-item; non-critical, governed by NG-1 + the CARVE.)*
- Q: Who is the human that "approved" the settlement command the Connector posts? →
  A: **A settlement / cash application is performed by a Console accounts/admin
  operator** (DP-2 `users.id`, G10 boundary) — **not** a cashier (DP-2 035 §OQ-7);
  the cashier captures intent only. The **payer** (insurer / corporate / credit
  customer) is an **account record, not a system principal**. These are recorded as
  **upstream provenance** on the posting command, not as Connector actors (§4).
  *(Rationale: DP-2 035 §2 + §8; non-critical, an actor-provenance default.)*
- Q: Does the Connector compute any VAT / tax when posting? → A: **No — tax is
  activation-only (ADR-0003, G6); the Connector posts the tax-pending placeholder
  the command carries and invents no VAT allocation.** *(Rationale: DP-2 035 §6 /
  FR-023 / NG-4; non-critical.)*
- **CRITICAL-1** — Q: Does the **012 posting-feed** (the Connector's actual
  consumption surface) already carry a settlement / Payment-Entry / receivable /
  claim work-item kind to post? → A: **NO — not yet (E-4).** The 012
  `PostingWorkItem.kind` enum is **`[sale_post, reversal]` only**, and the contract
  states the Payment Entry "is deferred until a DP2 payments model lands, at which
  point the work-item payload + this contract gain the tender fields (a versioned,
  backward-compatible extension)." DP-2 035 has now landed the settlement *model* +
  G2 contract, but the **012 feed has not yet been extended** with a settlement
  posting work-item kind. **Provisional default (does NOT block this SPECIFY):** 009
  is specified to consume a **future, versioned, backward-compatible 012 extension**
  that DP-2 authors (carrying the approved settlement / cash-application / claim /
  remittance command + `erpnextPaymentEntryRef`); 009 authors **no** part of that
  extension. **Escalated (§11 OQ-1):** the exact shape / kind of that 012 extension
  is an upstream DP-2 decision and a hard precondition (G2-feed) before 009
  implements. *(Critical because it touches the contract surface the Connector
  consumes.)*

---

## Evidence basis (verified read-only, `origin/main`, 2026-06-16)

| Repo | What was read | Key finding |
|---|---|---|
| Data-Pulse-2 | `specs/035-sale-settlement-and-receivables-model/spec.md` | E-1 |
| Data-Pulse-2 | `packages/contracts/openapi/settlement/settlement.yaml` (G2, RATIFIED) | E-2 |
| Data-Pulse-2 | `packages/contracts/openapi/erpnext-connector/posting-feed.yaml` (012) | E-4 |
| Retail-Tower-ERP-Next-Connector | `specs/006-sales-posting-adapter/spec.md` | E-3 |
| Retail-Tower-Orchestrator | CLAUDE.md architecture invariant; `docs/gates/cross-repo-gates.md` (cited) | E-5 |

- **E-1 (parent producer is SPECIFY-only, but G2 is RATIFIED).** DP-2 035 defines
  the settlement-and-receivables model and explicitly names the five children,
  including *"Connector 009 — receivables-and-third-party-posting-adapter: consumes
  approved posting commands; later consumer (FR-018)."* It states the Connector
  *"posts approved settlement / receivable / claim financial movements to ERPNext;
  it is never in the POS capture or auth path"* (FR-018) and that *"ERPNext
  Payment-Entry posting stays gated behind 011-DR-POSTING-R1"* (§OQ-7). The reversal
  carve (NG-1, §OQ-4) routes void/refund/rejection to DP-026 + Connector Arc A +
  POS-014, **not** to a new workflow.
- **E-2 (the G2 contract of record — the upstream SOURCE of the facts 009 posts).**
  `settlement/settlement.yaml` (`1.0.0-draft`) defines 8 operations. The
  **management surface** (`cookieAuth` Console / `operatorAuthorization` POS) is
  **NOT** the Connector's HTTP client — it is the producer of the facts:
  - `consoleApplyPayment` — DP-2-owned cash application (7-C, the operational truth)
    → the **ERPNext Payment Entry** is the downstream **valuation projection**,
    referenced by `Receivable.erpnextPaymentEntryRef`, *"populated only once the
    connector posting gate (011-DR-POSTING-R1) clears — null until then."* **This is
    the core of 009 — the exact Payment-Entry posting connector 006 deferred.**
  - `posRecordSettlementIntent` → opens receivable(s) (invoice / outstanding-AR
    provenance); `consoleGetReceivable` / `consoleListReceivables` are the
    `Receivable` projections (state machine `open -> partially_applied -> settled ->
    claimed -> flagged`; `reversal_consumed` **excluded** by the §OQ-4 CARVE).
  - `consoleSubmitClaim` (→ `Claim`) + `consoleReconcileRemittance`
    (→ `ReconciliationResult`) → claim / remittance valuation postings.
  - Money is exact-decimal string; every write is `Idempotency-Key`-idempotent.
- **E-3 (connector 006 owns the Sales Invoice and DEFERRED the Payment Entry).**
  Connector `006` posts a **submitted Sales Invoice** over the 012 pull/ack surface,
  **applying** the DP-2-pre-resolved `erpnextItemRef` (it resolves nothing). Per the
  signed rider `011-DR-POSTING-R1`, the *"first implementation slice is submitted
  Sales Invoice / outstanding-AR only … Payment Entry is deferred and gated until a
  DP2 tender/payment fact model, a 012 payment extension, idempotent Payment-Entry
  support, and payment repair/reconciliation semantics all land."* **009 is the
  slice that lands the receivables / cash-application Payment-Entry posting**
  (`consoleApplyPayment`) — distinct from the cash-at-till **tender** PE, which
  remains a separately-deferred 006 / 012 item — and it does **not** re-post the
  invoice.
- **E-4 (the 012 transport surface for settlement does NOT yet exist — CRITICAL-1).**
  `posting-feed.yaml` (`1.1.0-draft`) is the only DP-2↔Connector boundary
  (`connectorPullPostings` pull + `connectorAckOutcome`, opaque revocable
  `connectorBearer`). Its `PostingWorkItem.kind` enum is **`[sale_post, reversal]`
  only**. The contract states the Payment Entry *"is deferred until a DP2 payments
  model lands, at which point the work-item payload + this contract gain the tender
  fields (a versioned, backward-compatible extension)."* The settlement model (035)
  has landed; **the 012 feed extension carrying a settlement / Payment-Entry
  work-item has not.** 009 consumes that future extension; it authors none of it.
- **E-5 (architecture invariant + gates).** CLAUDE.md and DP-2 035 §0 pin
  `POS -> DP-2 -> Connector -> ERPNext`; the Connector reaches DP-2 only via the 012
  boundary. The connector gate vocabulary (G2 contract / G3 migration / G10 identity
  / G4 secret) is defined in the Orchestrator's `docs/gates/cross-repo-gates.md` and
  is **distinct** from DP-2 035's own work-package G-letters (035 §10 warns of this).

---

## 1. Summary

Today the Connector posts a **forward sale fact** — connector `006` turns a
validated DP-2 sale work-item into a **submitted ERPNext Sales Invoice** over the
012 posting-feed, applying the DP-2-pre-resolved `erpnextItemRef`. It deliberately
**stopped short of the money**: the Payment Entry was deferred (E-3), so the
interim state is an unpaid / outstanding Sales Invoice.

DP-2 035 has now landed the **settlement-and-receivables model** and its **G2
contract** (`settlement/settlement.yaml`, RATIFIED). That model is where the
**money owed** lives past the transaction: a **receivable** against a **payer
account** (credit customer / corporate / insurer), advanced by **cash application**
(`consoleApplyPayment`, the DP-2-owned operational truth), and — for insurer payers
— by a **claim → remittance → reconciliation** cycle. Critically, the contract
already reserves `Receivable.erpnextPaymentEntryRef` as the **external reference to
the ERPNext Payment Entry** — the valuation projection ERPNext owns — *"null until
the connector posting gate (011-DR-POSTING-R1) clears."*

This feature defines the **Connector child (009)** that clears that gap: the later
consumer that, when DP-2 projects an **approved** settlement posting command onto
the 012 feed, posts the corresponding **ERPNext accounting document** — the
**Payment Entry** for a cash application, and the claim / remittance valuation
movements — keeping ERPNext as a reconciled valuation projection while DP-2 remains
the operational source of truth.

> **Two distinct deferred Payment Entries — do not conflate.** 009's Payment Entry is
> the **cash-application** PE: a receivable settled later by a payer who is **not the
> person at the counter** (`consoleApplyPayment`; DP-2 035 §1). It is **not** the
> **cash-at-till tender** PE that 006 / 012 separately deferred (012 lines 46–52:
> "008 models NO tender … deferred until a DP2 payments model lands"). The cash-at-till
> tender PE remains a **separately-deferred 006 / 012 item** even after 009 ships; 009
> scopes only the receivables / cash-application PE (FR-001), not the till-tender PE. It is **idempotent** (012 ack semantics) and
**upgrade-safe** (Retail-Tower-terms mapping, never ERPNext doctype field names, so
a v15→v16 change alters internal mapping only — 012 O-6).

### Core principle (stated once)

> **DP-2 owns the operational settlement truth; ERPNext owns the valuation
> projection; the Connector is the one-way adapter between them.** The Connector
> posts what DP-2 has already **decided and approved** over the 012 boundary; it
> makes **no** settlement decision, applies **no** cash, authorizes **no**
> receivable, and never edits a posted document — a reversal is a NEW document via
> Arc A (NG-1).

---

## 2. Goals

- **G-1.** Define the **Payment-Entry posting** the Connector creates in ERPNext
  when DP-2 projects an **approved cash application** (`consoleApplyPayment`, 7-C)
  onto the 012 feed — the slice connector `006` deferred (E-3) — keyed to
  `Receivable.erpnextPaymentEntryRef` (E-2).
- **G-2.** Define the **claim / remittance valuation posting** the Connector creates
  for a reconciled `ReconciliationResult` (settled / partial / flagged), at
  product-contract level only.
- **G-3.** Keep the carve clean: **006 owns the Sales Invoice** (forward AR); **009
  adds the Payment Entry + claim/remittance valuation** against it — no
  double-posting of the invoice.
- **G-4.** Reuse **Connector Arc A** (+ DP-026 + POS-014) for any void / refund /
  insurance-rejection — **no parallel reversal model** (NG-1).
- **G-5.** Consume DP-2 **only** via the **012 posting-feed** boundary
  (`connectorPullPostings` / `connectorAckOutcome`, `connectorBearer`); **never**
  call `settlement.yaml`'s Console / POS routes (architecture invariant).
- **G-6.** **Idempotent & upgrade-safe** posting: rely on the 012 ack idempotency
  (re-acking a work-item never double-posts) and speak Retail-Tower terms, never
  ERPNext doctype field names (012 O-6), so an ERPNext upgrade is mapping-internal.
- **G-7.** Post **tax-pending**: carry the placeholder the command holds, compute no
  VAT allocation (ADR-0003 / G6 — NG-4).

---

## 3. Non-Goals (explicit)

- **NG-1 — No parallel/competing reversal model.** Void / refund / insurance-
  rejection reuse **Connector Arc A** + DP-026 + POS-014. 009 posts forward
  invoices / Payment Entries; reversal credit notes are Arc A's (E-1, §OQ-4 CARVE).
- **NG-2 — No DP-2 file authored or modified.** `settlement.yaml`, `posting-feed.yaml`,
  and every DP-2 contract / migration are upstream dependencies (E-2/E-4); 009
  conforms / consumes, it does not author.
- **NG-3 — No implementation.** No connector / Frappe code, `hooks.py` edit, poller,
  posting worker, DocType, DB schema, migration, test, OpenAPI YAML, generated
  client, package/lock, CI, secret, or env in this artifact.
- **NG-4 — No VAT / tax allocation.** Tax is activation-only (ADR-0003, G6); the
  Connector posts the tax-pending placeholder, inventing no allocation (E-1 §6).
- **NG-5 — No re-post of the Sales Invoice.** Connector `006` owns the submitted
  Sales Invoice (E-3); 009 adds the Payment Entry / claim valuation against it.
- **NG-6 — No authority handover.** ERPNext stays valuation / back-office; DP-2 owns
  the operational settlement state. `erpnextPaymentEntryRef` is a non-authoritative
  pointer (E-2; Constitution §I/§III/§IX).
- **NG-7 — No new credential / auth scheme.** Posting reuses the connector boundary
  (018 / 028 §15 `connectorBearer`, scope `connector`); device / POS / human
  credentials are rejected.
- **NG-8 — No item / warehouse / account resolution.** As in connector `006`
  (rider R2–R5), the Connector **applies** DP-2-pre-resolved references and never
  resolves, infers, or holds a second copy of a mapping.

---

## 4. Actors & surfaces

> The Connector's **direct** actors are narrow (a machine adapter). The settlement
> human roles are **upstream provenance** carried on the approved command, not
> Connector actors (DP-2 035 §2/§8; Clarifications).

| Actor / surface | Role in this feature |
|---|---|
| **Connector (Frappe app, machine principal)** | The ONLY direct actor: pulls an approved settlement posting work-item over 012, posts the ERPNext Payment Entry / claim valuation, and acks the outcome. Authenticates as a `connector`-scoped revocable machine bearer (018 / 028 §15). |
| **Data-Pulse-2 backend (authority)** | Owns settlement state, cash application (7-C), receivable lifecycle, and the **approval** that places a posting command on the 012 feed. The Connector posts only what DP-2 approved. *(Provenance, not a Connector-side actor.)* |
| **ERPNext / Frappe (valuation target)** | Receives the posted Payment Entry / valuation document. A reconciled projection, never the source of truth (NG-6). |
| **Console accounts / admin operator (human, upstream)** | Performs the cash application (`consoleApplyPayment`) / claim submission in DP-2 (G10). Provenance on the command — **not** a Connector actor. |
| **Cashier / POS operator (human, upstream)** | Captures settlement **intent** only (`posRecordSettlementIntent`) — never authorizes or posts. Provenance only. |
| **Payer (insurer / corporate / credit customer)** | An **account record**, not a system principal (DP-2 035 §2 / OQ-7). Modeled as `payerRef`; never authenticates. |
| **Connector Arc A (reuse)** | The existing forward-feed reversal posting path (NG-1). Consumes void/refund/rejection outcomes; 009 builds no parallel path. |

---

## 5. User Scenarios & Testing *(mandatory)*

### User Story 1 — Post an approved cash application as an ERPNext Payment Entry (Priority: P1)

When DP-2 records a cash application against a receivable (`consoleApplyPayment`,
7-C operational truth) and **approves** it for posting, it projects an approved
settlement posting command onto the 012 feed. The Connector pulls it
(`connectorPullPostings`), posts a corresponding **ERPNext Payment Entry** against
the existing Sales Invoice (the one connector `006` posted), and acks the outcome
(`connectorAckOutcome`) carrying the ERPNext document reference — which is what
populates `Receivable.erpnextPaymentEntryRef` upstream.

**Why this priority**: This is the reason 009 exists — the **deferred Payment Entry**
from connector `006` (E-3), and the thing DP-2 035 §OQ-7 named as the connector's
job. P1 delivers the producer's core contract intent: approved cash application →
ERPNext Payment Entry → `erpnextPaymentEntryRef` populated.

**Independent Test**: Reviewable as policy — given an approved cash-application
posting command on the 012 feed (once the feed carries it, CRITICAL-1), the
documented posting path produces exactly **one** ERPNext Payment Entry referencing
the existing Sales Invoice, addressed generically as `{doctype, name}`, with the ERP
document ref returned via `connectorAckOutcome` as `outcome = posted`. No code is
run.

**Acceptance Scenarios**:

1. **Given** an approved cash-application posting command (full clearing payment) on
   the 012 feed, **When** the Connector posts it, **Then** the model defines exactly
   one ERPNext Payment Entry applied against the existing Sales Invoice, and the
   work-item is acked `posted` with the document ref (feeding
   `Receivable.erpnextPaymentEntryRef`) — **without** re-posting the invoice (NG-5).
2. **Given** the same work-item re-pulled / re-acked with the same key, **When**
   reprocessed, **Then** the model requires **no duplicate** Payment Entry (012 ack
   idempotency; G5), and `idempotency_key_conflict` on a key reused with a different
   outcome.
3. **Given** a partial cash application, **When** posted, **Then** the model defines
   a Payment Entry for the partial amount leaving the invoice partially outstanding,
   consistent with the upstream `partially_applied` receivable state.

---

### User Story 2 — Post a claim / remittance reconciliation valuation (Priority: P2)

For an insurer / corporate payer, DP-2 reconciles a remittance against a claim
(`consoleReconcileRemittance` → `ReconciliationResult` of `settled | partial |
flagged`) and approves the resulting valuation movement for posting. The Connector
pulls the approved command and posts the corresponding ERPNext valuation document(s)
against the claimed receivable(s).

**Why this priority**: Claim / remittance is the most complex payer path and depends
on the receivable + Payment-Entry model (US1) being defined first, so it is P2.

**Independent Test**: Reviewable by walking a reconciled claim (full / partial /
flagged) through the model and confirming the Connector posts the matching ERPNext
valuation movement and acks it, and that a **rejected** line routes to Arc A reuse
(US3), not to a new posting kind here.

**Acceptance Scenarios**:

1. **Given** an approved `settled` reconciliation command, **When** posted, **Then**
   the model defines the ERPNext valuation movement that clears the claimed
   receivable(s), acked `posted` with variance recorded as zero.
2. **Given** an approved `partial` reconciliation command, **When** posted, **Then**
   the model defines a valuation movement for the remitted amount leaving a recorded
   outstanding balance + variance.
3. **Given** a `flagged` outcome (net-zero-or-below / anomaly), **When** processed,
   **Then** the model defines a deterministic safe posting outcome (post-as-flagged
   / hold for review), never an indeterminate one (DP-2 035 §4 edge cases).

---

### User Story 3 — A rejected claim line reverses via Arc A, not a new path (Priority: P3)

When an insurer rejects a claim line, DP-2 routes the rejection to the existing
reversal surfaces (DP-026 + POS-014). The Connector's reaction is to post a **NEW
reversing document** through **Connector Arc A** — a credit note / return invoice —
never an edit of the posted Payment Entry or invoice, and never a new 009-specific
reversal kind.

**Why this priority**: Reversal correctness is essential but is **reuse** (NG-1), so
it is documented as a routing requirement (P3), not a new posting model.

**Independent Test**: Reviewable by confirming that a rejected line is posted via
Arc A's existing forward-feed reversal (the 012 `kind: reversal` work-item), that
009 defines **no** competing reversal posting kind, and that DP-026 + POS-014 are
named as the reuse anchors.

**Acceptance Scenarios**:

1. **Given** an insurer-rejected claim line, **When** the rejection reaches the
   feed, **Then** the model **routes it to Connector Arc A** (a NEW reversing
   document) and defines **no** new 009 reversal kind (NG-1).
2. **Given** a reversal of a sale whose receivable 009 had posted a Payment Entry
   for, **When** Arc A posts the reversing document, **Then** the model defines the
   receivable as **consuming** that reversal outcome upstream (DP-2), never 009
   re-deriving it (E-1 §4 edge case; OQ-4).

---

### Edge Cases

- **Settlement work-item kind absent from the 012 feed (CRITICAL-1).** Until DP-2
  extends the 012 feed with a settlement posting work-item kind, there is **nothing
  for 009 to pull** — implementation is blocked on that upstream extension (OQ-1).
- **Approved-but-no-invoice.** A cash-application command whose Sales Invoice was not
  yet posted by connector `006` must have a defined ordering / hold outcome — 009
  never invents an invoice (NG-5/NG-8).
- **Replay / duplicate.** A re-pulled or re-acked settlement work-item must never
  double-post (012 ack idempotency; G5).
- **Over-application / stale state upstream.** Over-application is a DP-2-side `409`
  on `consoleApplyPayment` (E-2) — it never reaches the feed as an approved command;
  009 posts only approved commands.
- **Cross-tenant / out-of-scope work-item ref.** Non-disclosing `not_found` per the
  012 boundary (no existence leak; §II/§XII).
- **Tax-pending.** Any tax carrier on the command is a placeholder; 009 posts it
  verbatim and computes no VAT (NG-4).
- **ERPNext closed period / unmapped account.** A permanent ERPNext rejection acks
  `permanently_rejected` with a structured reason (012 vocabulary); DP-2 owns the
  resulting DLQ / reconciliation state — 009 never silently drops it.

---

## 6. Requirements *(mandatory)*

### Functional Requirements — Posting Model (Payment Entry / cash application)

- **FR-001**: The Connector MUST post an **ERPNext Payment Entry** when DP-2 projects
  an **approved cash-application** posting command onto the 012 feed, applied against
  the existing Sales Invoice that connector `006` posted (E-2/E-3; the deferred
  slice). It MUST NOT re-post or edit the Sales Invoice (NG-5).
- **FR-002**: The posted Payment Entry's ERPNext document reference MUST be returned
  to DP-2 via `connectorAckOutcome`, so DP-2 can populate
  `Receivable.erpnextPaymentEntryRef` (the non-authoritative valuation pointer, E-2).
- **FR-003**: A **partial** cash application MUST post a Payment Entry for the
  partial amount, consistent with the upstream `partially_applied` receivable state,
  leaving the invoice partially outstanding (E-2).

### Functional Requirements — Posting Model (claim / remittance valuation)

- **FR-004**: The Connector MUST post the ERPNext valuation movement matching an
  **approved `ReconciliationResult`** (`settled | partial | flagged`) against the
  claimed receivable(s) (E-2 `consoleReconcileRemittance`).
- **FR-005**: A **rejected** claim line MUST route to **Connector Arc A** (a NEW
  reversing document) + DP-026 + POS-014; 009 MUST define **no** competing reversal
  posting kind (NG-1; FR-015 of DP-2 035).

### Functional Requirements — Consumption boundary & idempotency

- **FR-006**: The Connector MUST consume settlement posting commands **only** over
  the **012 posting-feed** boundary (`connectorPullPostings` / `connectorAckOutcome`,
  `connectorBearer`). It MUST NOT call `settlement.yaml`'s Console (`cookieAuth`) or
  POS (`operatorAuthorization`) routes, nor make any other ERPNext-bound egress
  except to its own ERPNext site (architecture invariant; G-5).
- **FR-007**: Posting MUST be **idempotent** via the 012 ack semantics — a re-pulled
  or re-acked settlement work-item never produces a duplicate ERPNext document, and a
  key reused with a different outcome yields `idempotency_key_conflict` (G5).
- **FR-008**: The Connector MUST post only **approved** commands DP-2 placed on the
  feed; it MUST make no settlement decision, apply no cash, and authorize no
  receivable (Core Principle; G-1/G-5).

### Functional Requirements — Upgrade-safety, mapping, tax

- **FR-009**: The Connector MUST address every ERPNext document generically as
  `{doctype, name}` and speak **Retail-Tower terms**, never ERPNext doctype field
  names, so an ERPNext v15→v16 change is mapping-internal (012 O-6; G-6).
- **FR-010**: The Connector MUST **apply** DP-2-pre-resolved references (item /
  warehouse / account / payer) and MUST NOT resolve, infer, reach back into DP-2
  for, or hold a second copy of any mapping (NG-8; connector `006` rider R2–R5).
- **FR-011**: The Connector MUST carry tax as a **placeholder only**, computing no
  VAT allocation (ADR-0003 / G6; NG-4).

### Functional Requirements — Failure, audit, isolation

- **FR-012**: A permanent ERPNext rejection (closed period / unmapped account /
  validation) MUST ack `permanently_rejected` with a structured reason (012
  vocabulary); DP-2 owns the resulting DLQ / reconciliation state — 009 never
  silently drops a work-item.
- **FR-013**: Every posting attempt + outcome MUST be **auditable** (work-item ref,
  ERPNext document ref, outcome, time) and emit posting-health observability,
  consistent with connector `006` + 012; secrets never logged (G4).
- **FR-014**: All work-items MUST be **tenant / store scoped** via the
  `connectorBearer` principal; a cross-tenant / out-of-scope ref is a non-disclosing
  `not_found` (012 boundary; §II/§XII).

### Functional Requirements — Gate & dependency posture

- **FR-015**: This feature MUST mark **no** gate satisfied. The Connector posting is
  gated behind **011-DR-POSTING-R1** (DP-2 035 §OQ-7), and the **012 settlement
  work-item extension** (CRITICAL-1 / OQ-1) is a hard upstream precondition. Both,
  plus the connector gates (G2 / G3 / G10 / G4), are **required before implement**
  and are tracked in §10.
- **FR-016**: This feature MUST author **no** DP-2 file and **no** OpenAPI YAML; it
  consumes the RATIFIED `settlement.yaml` (G2) and the future 012 extension (NG-2).

### Key Entities *(contract-intent level; consumed from upstream, not authored here)*

- **Approved Settlement Posting Command** — the future 012 feed work-item (a new
  `kind`, CRITICAL-1) carrying an approved cash application / claim / remittance the
  Connector posts. Authored by DP-2, not here.
- **Receivable (projection)** — `Receivable` from `settlement.yaml` (E-2): owed
  amount, state, `erpnextPaymentEntryRef`. Read context for the posting; never
  mutated by 009.
- **ERPNext Payment Entry** — the valuation document 009 posts for a cash
  application (the deferred-from-006 slice); referenced by `erpnextPaymentEntryRef`.
- **ERPNext Claim / Remittance Valuation Movement** — the document(s) 009 posts for
  a reconciled claim (`ReconciliationResult`).
- **Arc A Reversing Document** — the NEW credit note / return invoice posted via the
  existing Arc A path for a rejection / reversal (reuse; NG-1).

---

## 7. Conceptual Model / Schema Impact (G3 — conceptual ONLY)

The eventual implementation is expected to introduce a Connector-side posting path
for the new settlement work-item kind (a poller branch + a Payment-Entry / valuation
mapping module), plus possibly an additive **Frappe `Connector Settings` DocType**
note for settlement-posting enablement. **This spec authors no migration, no
DocType, and no schema.** Per the connector convention, any Connector-side schema
delta is a **Frappe DocType change** applied by `bench migrate` (G3 discipline), not
hand-written SQL; the only SQL in the chain is DP-2-owned and upstream. G3 requires
the model impact be *identified* conceptually at planning; it is **not** built here
(NG-3, FR-015).

---

## 8. Identity / Access Implications (G10)

- The Connector posts as a **`connector`-scoped, revocable machine bearer**
  (`connectorBearer`, 018 / 028 §15) on the 012 boundary. A POS device / operator
  credential or a human cookie session is **rejected** (scope non-interchangeability,
  028 SR-10; NG-7).
- The Connector **never** holds or presents a `cookieAuth` or `operatorAuthorization`
  credential and never calls `settlement.yaml`'s management routes (architecture
  invariant; FR-006).
- Cross-tenant access to any work-item is a non-disclosing `not_found` (012; §II/§XII).
- 401/403 semantics are owned by 028 (G10) and are NOT re-decided here.

---

## 9. Audit & Observability Expectations

- **Auditability (Constitution §XIII).** Every posting attempt records the work-item
  ref, the ERPNext document ref, the discrete outcome, and time; the posted document
  is reconstructable from the audit trail. Secrets are never logged (G4).
- **Observability (Constitution §VII).** Posting-health signals (settlement-posting
  throughput, permanent-rejection rate, ack-retry counts) are anticipated; exact
  metric names are defined in the later implementation slice, not here, consistent
  with connector `006` + 012.

---

## 10. Gate Mapping

> Connector cross-repo gate vocabulary (Orchestrator `docs/gates/cross-repo-gates.md`,
> E-5) — **distinct** from DP-2 035's own work-package G-letters (DP-2 035 §10).
> This spec marks **NONE** satisfied.

| Gate | Meaning (connector vocabulary) | Status in this SPECIFY/plan/tasks artifact |
|------|--------------------------------|--------------------------------------------|
| **G2** | Contract Gate — the contracts 009 consumes are pinned & ratified. | **Dependency available per cited evidence (NOT re-certified here).** Upstream `settlement.yaml` G2 is RATIFIED (DP-2 035 §10, PR #574, `cb4a7e5`); the **012 settlement work-item extension** 009 actually pulls **does NOT yet exist** (E-4, CRITICAL-1) — so the *consumption* contract surface is **NOT complete**. 009 authors no contract (NG-2). **NOT satisfied for 009's consumption.** |
| **G3** | Migration Gate — Connector-side schema delta identified conceptually only. | **NOT satisfied.** Model impact framed in §7; no DocType / migration authored (NG-3, FR-015). |
| **G10** | Identity & Access Boundary Gate — connector boundary respected. | **NOT satisfied (must be verified before dispatch).** §8 / FR-006 / FR-014 reuse the `connectorBearer` boundary + 028 §15; 028 boundary decisions MUST be signed + G10 verified before any implementation. |
| **G4** | Security Gate — secret handling, no-logging, least-privilege. | **NOT satisfied (adjacent; noted).** §9 / FR-013 conform to the existing 003 G4 secret discipline; not built out here. |
| **011-DR-POSTING-R1** | Owner rider — ERPNext Payment-Entry posting authorization. | **NOT satisfied — the hard gate on 009's core (DP-2 035 §OQ-7).** The Payment-Entry posting (FR-001) stays gated behind this rider; this spec does not lift it. |

---

## 11. Open Questions

- **CRITICAL — OQ-1 (012 settlement work-item extension).** The 012 posting-feed
  `PostingWorkItem.kind` is **`[sale_post, reversal]` only** today (E-4); it carries
  **no** settlement / Payment-Entry / claim work-item. The exact shape and `kind` of
  the **future versioned, backward-compatible 012 extension** that carries the
  approved settlement command (+ `erpnextPaymentEntryRef`, tender / cash-application
  / reconciliation fields) is an **upstream DP-2 decision** and a **hard precondition**
  before 009 implements. **Provisional default:** 009 is specified to consume that
  future extension and authors none of it. *(Critical: it defines the contract
  surface the Connector consumes.)*
- **CRITICAL — OQ-2 (posting authorization rider).** Lifting **011-DR-POSTING-R1**
  for the Payment-Entry posting (FR-001) is an owner decision; this spec assumes it
  remains gated. *(Critical: it gates the core deliverable.)*
- **OQ-3 (claim / remittance valuation document shape).** The exact ERPNext
  document(s) for a claim / remittance valuation (Payment Entry vs Journal Entry vs
  a credit/debit note) is a plan-phase mapping decision; framed conceptually only
  (§5 US2). *(Non-critical: a mapping detail, not a contract-surface change.)*
- **OQ-4 (reversal-consumed sequencing).** How a receivable that 009 posted a
  Payment Entry for **consumes** a later DP-026 reversal (via Arc A) is the §OQ-4
  CARVE — reversal-compatibility fields remain deferred upstream until DP-026 closes
  (E-1). 009 reuses Arc A and adds no parallel path. *(Non-critical: governed by
  NG-1 + the upstream CARVE.)*

---

## 12. Dependency Mapping

### Upstream dependencies (this feature relies on; verified `origin/main`)

- **DP-2 035** (parent producer) + **`settlement.yaml`** G2 (RATIFIED, PR #574,
  `cb4a7e5`) — the contract of record producing the receivable / cash-application /
  claim / remittance facts (E-1/E-2).
- **DP-2 012 `posting-feed.yaml`** — the **only** DP-2↔Connector boundary; **requires
  a future settlement work-item extension** (E-4, CRITICAL-1 / OQ-1) before 009 can
  pull anything.
- **Connector 006 (sales-posting-adapter)** — owns the submitted Sales Invoice 009
  posts the Payment Entry against; 009 lands 006's **deferred** Payment Entry (E-3).
- **Connector Arc A** (+ **DP-026** + **POS-014**) — the reuse anchors for
  reversal / rejection (NG-1; FR-005).
- **018 / 028 §15** — the `connectorBearer` machine-credential boundary (G10; §8).
- **011-DR-POSTING-R1** — the posting-authorization rider gating FR-001 (OQ-2).
- **ADR-0003** — tax activation-only posture (G6, §6; NG-4).

### This feature's place

- **Connector child (009)** of the settlement work package; the **last** posting
  consumer — it depends on the parent contract (G2) **and** the 012 extension
  (OQ-1) **and** the 006 Sales Invoice. Fully blocked until those clear.

---

## 13. Claim Ceiling / Status Honesty

- This is a **SPECIFY + clarify + plan + tasks** artifact at **Proposed / Draft**
  status. It produces **no** code, OpenAPI, migration, DocType, or DP-2 file.
- It marks **NO** gate satisfied. The Payment-Entry posting stays gated behind
  **011-DR-POSTING-R1** (OQ-2), and the **012 settlement work-item surface 009
  consumes does not yet exist** (CRITICAL-1 / OQ-1).
- The upstream `settlement.yaml` G2 is RATIFIED — that is **upstream evidence**, not
  a 009 gate; 009 re-certifies nothing.
- Nothing here has been built, run, or dispatched. Any reader treating the
  Payment-Entry posting or the 012 settlement feed as existing is reading more than
  this artifact claims.

---

## 14. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can trace each consumed `settlement.yaml` operation
  (`consoleApplyPayment` → Payment Entry; `consoleReconcileRemittance` →
  claim/remittance valuation; receivable projections) to an explicit FR — and
  confirm 009 calls **none** of them directly (architecture invariant) — in under 2
  minutes.
- **SC-002**: A reviewer can confirm the **006 ↔ 009 carve** is unambiguous: 006
  owns the Sales Invoice, 009 adds the deferred Payment Entry / claim valuation, no
  double-post (NG-5).
- **SC-003**: A reviewer can confirm the reversal non-goal is unambiguous — no
  competing reversal model; Arc A + DP-026 + POS-014 are the named reuse anchors
  (NG-1) — in under 2 minutes.
- **SC-004**: All connector gates (G2 / G3 / G10 / G4) **and** the
  **011-DR-POSTING-R1** rider are mapped with a status, and **none** is marked
  satisfied; both critical OQs (012 extension; rider) are captured with blocking
  semantics.
- **SC-005**: A reviewer can confirm the spec authors **zero** OpenAPI / DP-2 /
  migration / code, and that it documents the **012 settlement work-item gap**
  (CRITICAL-1) as a hard upstream precondition, consistent with the claim ceiling
  (§13).

---

## 15. Assumptions

- The architecture invariant (`POS -> DP-2 -> Connector -> ERPNext`; Connector
  reaches DP-2 only via the 012 boundary) holds and is not redefined here.
- `settlement.yaml` (G2) and connector `006`'s Sales Invoice posting exist and are
  reused; 009 does not redefine them.
- DP-2 will author the **future versioned 012 extension** carrying the settlement
  posting work-item (CRITICAL-1 / OQ-1); 009 authors none of it.
- Connector Arc A + DP-026 + POS-014 remain the canonical reversal surfaces; 009
  consumes their outcomes (NG-1).
- ERPNext stays valuation / back-office; DP-2 owns operational settlement state.
- Tax remains deactivated (tax-pending) until G6 activation under ADR-0003.
- Exact ERPNext document shapes, mapping modules, metric names, and the 012
  extension shape are left to the plan phase and the upstream DP-2 slice; this spec
  is product / contract-consuming intent only.
