# Feature Specification: Sales Posting Adapter (POS/Sales Invoice creation from DP2 sale commands)

**Feature Branch**: `feat/con-006-sales-posting-adapter-spec`

**Feature ID**: 006

**Short name**: sales-posting-adapter

**Created**: 2026-06-05

**Status**: Draft — planning / policy, docs-only (no connector code, no hooks.py edit, no migration)

**Constitution version**: 1.0.1

**Input**: README roadmap item **006 — Sales Posting Adapter** ("Create ERPNext sales documents
from validated Data-Pulse sale commands"). This spec is **RESCOPED** per the orchestrator decision
`Q-CON-004` (Wave-A ratification, 2026-06-05) and the **signed** Data-Pulse-2 rider
`011-DR-POSTING-R1` (R1–R5): the connector performs **NO connector-side item resolution** — it
**applies** the DP2-pre-resolved `erpnextItemRef` carried on each offered sale line. The adapter
consumes the merged 012 posting-feed contract over the fixed two-operation pull/ack surface; it
authors no OpenAPI, no Frappe implementation code, and no `hooks.py` edit in this lane.

---

## 0. What this spec is (and is not)

This is the **planning / policy spec** for connector spec 006 — how the connector turns a
Data-Pulse-2 posting work-item (a validated 008 sale projection) into an ERPNext sales document
over the fixed 012 posting-feed contract.

It is **docs / policy only**:

- No Frappe / connector implementation code (no resolution code, no poller, no posting worker).
- **No `hooks.py` edit.** The poller this adapter will register is recorded here as a *planned*
  `scheduler_event` (see §8) — it is NOT wired in this slice. `hooks.py` deliberately stays empty
  at this layer (spec 001 FR-005, constitution Principle VII).
- No OpenAPI authoring (the 012 posting-feed contract is owned by Data-Pulse-2 and is cited, not
  re-derived — FR-013, Principle I).
- No DB schema, no migration, no package/lock file, no CI.

Like connector spec 004 and DP2's 011/012/013/015 spec PRs, this spec ships with **companion
documents but no `plan.md`, `tasks.md`, `data-model.md`, or `execution-map.yaml`**, and **no
dispatchable code slices**. It establishes the posting model, the transport realisation, the
rescoped item-identity posture (apply, never resolve), idempotency / failure posture, the
implementation gates it inherits but does not satisfy, and the open items.

**Implementation stays blocked** behind the rest of the DP-015 arc (see §9) and the connector's own
Spec-Kit chain (`plan.md` → Constitution Check → any `[GATED]` schema → `tasks.md` →
`execution-map.yaml`).

Companion documents in this folder:

- [resolution-concepts.md](./resolution-concepts.md) — the rescoped item-identity posture
  (apply the pre-resolved `erpnextItemRef`; the connector-side lookup retired by `Q-CON-004` /
  rider R2), the posting decision table, and the UOM / money posture.
- [follow-up-notes.md](./follow-up-notes.md) — the inherited implementation gates, the planned
  `hooks.py` `scheduler_event` registration, the Payment-Entry sub-scope gated by rider R1, and
  forward references.

---

## Clarifications

### Session 2026-06-05

- Q: Does the connector resolve a sale line's product to an ERPNext Item at posting time
  (the connector spec 004 Option-A framing)? → A: **No — rescoped.** Per `Q-CON-004`
  (rescope-with-supersession, ratified Wave-A 2026-06-05) and signed rider `011-DR-POSTING-R1`
  R2, **item resolution is DP2-side** at work-item projection (via the confirmed 013
  `erpnext_item_map`). The 012 posting-feed contract now carries a **required** `erpnextItemRef`
  (`{doctype:"Item", name}`) on every offered sale line. The connector **applies** that
  pre-resolved reference and MUST NOT look it up, infer it, reach back into DP2 for it, or hold a
  second copy of the mapping. Connector spec 004 FR-001/FR-003 (connector-side resolution) and the
  item-identity branch of its FR-006/US3 are **retired** by this supersession; connector 004's
  FR-002 (generic `{doctype, name}` addressing) and FR-008/US4 (UOM + money reconciliation) are
  **retained** and inherited here.
- Q: What is the first accepted posting model? → A: **Submitted Sales Invoice + associated Payment
  Entry** is the **signed target** (rider R1, unchanged). However, the **first implementation
  slice is an interim "submitted Sales Invoice / outstanding-AR only" mode** (rider R1): Payment
  Entry is **deferred and gated** until a DP2 tender/payment fact model, a 012 payment extension,
  idempotent Payment-Entry support, and payment repair/reconciliation semantics all land. The
  interim mode is **NOT finance-complete** and is expected to produce unpaid/outstanding ERPNext
  Sales Invoices — an expected interim state, not a defect.
- Q: How does the connector handle a line it cannot turn into an ERPNext Item? → A: **It never
  sees one.** Per rider R2, any line that cannot resolve to a confirmed 013 mapping
  **fails-to-DLQ in DP2 BEFORE the work-item is offered** — so every offered line already carries
  a resolved `erpnextItemRef`. There is **no "Misc"/substitute item** (rider R3) and an ad-hoc /
  unknown-item line still requires a confirmed 013 mapping before it can post (rider R4). The
  connector's failure posture (§US3) covers ERPNext-side and validation failures, NOT item
  resolution.
- Q: What about a missing warehouse mapping? → A: Per rider R5, an absent DP-014 warehouse mapping
  for a sale's store **fails-to-DLQ in DP2** (`unmapped_store`-class) before offer — the connector
  never guesses the ERPNext warehouse. The connector applies the pre-resolved store/warehouse
  identity the same way it applies `erpnextItemRef`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Post a validated DP2 sale command to ERPNext as a submitted sales document (Priority: P1)

When the connector pulls a posting work-item from Data-Pulse-2 over `connectorPullPostings`, it
MUST create the corresponding ERPNext sales document (interim: a submitted **Sales Invoice**),
mapping each sale line by **applying** the line's pre-resolved `erpnextItemRef`
(`{doctype:"Item", name}`), and addressing every ERPNext document generically as `{doctype, name}`
(connector 004 FR-002, Principle II) — never via a forked/field-level ERPNext model.

**Why this priority**: This is the core of the connector — the capture-UP path that turns a DP2
sale fact into ERPNext accounting truth. It is the reason the foundation (001–003), the mapping
posture (004), and the DP-015 arc exist. Defining the posting model now — before any posting code
— is the contract-first gate (Principle VII) and de-risks implementation.

**Independent Test**: Reviewable as policy: given a posting work-item whose lines each carry a
resolved `erpnextItemRef`, the documented posting path produces exactly one submitted ERPNext
Sales Invoice whose lines reference those Items generically, with the ERP document reference
returned to DP2 via `connectorAckOutcome` as `outcome = posted` carrying `documentRef`.

**Acceptance Scenarios**:

1. **Given** a posting work-item whose sale lines each carry a resolved `erpnextItemRef`,
   **When** the connector posts it, **Then** it creates one submitted ERPNext Sales Invoice whose
   lines reference the Items by the applied `{doctype:"Item", name}`, and acks `posted` with the
   ERPNext `documentRef`.
2. **Given** the work-item header, **When** the connector creates the document, **Then** it carries
   the DP2 `sourceSystem` + `externalId` provenance and money as exact-decimal + ISO-4217 currency
   (never float), per the 012 contract (`DecimalAmount` / `CurrencyCode`).
3. **Given** ERPNext, **When** the connector references any document (Item, Customer, Warehouse,
   the created Invoice), **Then** it uses the generic `{doctype, name}` form (Principle II), never a
   copied ERPNext field model.

---

### User Story 2 - Idempotent, retry-safe posting (Priority: P1, co-equal)

Replaying the same sale command MUST NOT create a duplicate ERPNext document. The connector MUST
key every post on the DP2 `sourceSystem` + `externalId` (the 012 wire idempotency anchor, O-3): the
same logical sale maps to the same ERPNext document, and an idempotent duplicate `posted` ack
echoes the existing `documentRef` unchanged (Principle IV).

**Why this priority**: Co-equal P1. At-least-once delivery across DP2 → connector → ERPNext is
inevitable; idempotency is what keeps the ledger correct. Gate G5 lands on this behavior. Defining
the replay key and the ack-replay rule now keeps implementation from re-litigating it.

**Independent Test**: Reviewable as policy: the spec states the replay key
(`sourceSystem`+`externalId`), that a re-offer of an already-posted work-item re-acks the SAME
`documentRef` (no second ERPNext document), and that the connector introduces NO new idempotency
primitive beyond the 012 contract's `Idempotency-Key` / O-3 semantics.

**Acceptance Scenarios**:

1. **Given** a work-item already posted (its `documentRef` recorded), **When** DP2 re-offers the
   same `sourceSystem`+`externalId`, **Then** the connector returns the SAME `documentRef` and
   creates no second ERPNext document (Principle IV / 012 O-3).
2. **Given** the `connectorAckOutcome` operation, **When** the same `Idempotency-Key` is reused
   with the SAME logical outcome, **Then** it replays deterministically; reuse with a DIFFERENT
   logical outcome returns `409 idempotency_key_conflict` — the connector does not invent a new
   idempotency mechanism.

---

### User Story 3 - Classify and surface posting failures explicitly, never silently (Priority: P1, co-equal)

When a post cannot complete, the connector MUST report a typed outcome over `connectorAckOutcome` —
`failed_transient` for a retryable failure (DP2 re-offers) or `permanently_rejected` (carries a
structured `reason` from DP2's **closed** `RejectionReason.category` set) — and MUST NOT post a
partial document, guess, or silently drop the work-item. A failed post MUST be repairable without
modifying the original DP2 sale fact (Principle VI / IV).

**Why this priority**: Co-equal P1. Principle VI ("fiscal & stock truth is never hidden") makes the
unhappy path first-class. A posting that fails silently is unoperatable; a typed outcome lets DP2's
017 reconciliation act. **Note (rescope):** item-resolution failure is NOT in this taxonomy — per
rider R2 an unresolvable line fails-to-DLQ in DP2 before offer, so the connector never emits an
item-resolution rejection for an *offered* line. This US3 covers ERPNext-side / validation /
closed-period / transient failures.

**Independent Test**: Reviewable as policy: every failure lands in exactly one typed outcome
(`failed_transient` XOR `permanently_rejected`), `permanently_rejected` carries
`reason.category` from the 012 closed set (`validation | closed_period | unmapped_item |
unmapped_account | other`) with NO new wire reason invented, and no silent partial/guess/drop path
exists. The original DP2 sale fact is never mutated by a failure ack (012 O-3).

**Acceptance Scenarios**:

1. **Given** a transient ERPNext failure (timeout, lock, temporary unavailability), **When** the
   post fails, **Then** the connector acks `failed_transient` and DP2 re-offers — the connector
   does NOT self-retry-loop (DP2 owns re-drive + DLQ + 017 reconciliation).
2. **Given** a non-retryable failure (e.g. a closed accounting period, a validation failure, an
   unmapped account), **When** the post fails, **Then** the connector acks `permanently_rejected`
   with the matching `reason.category` and posts nothing — DP2's 017 flag becomes actionable.
3. **Given** any failure ack, **When** it is reported, **Then** the original DP2 sale fact is not
   mutated, no ERPNext document is partially created, and the message carries no secret/token/
   credential or sensitive ERPNext internals (Principle V / Gate G4).

---

### User Story 4 - Reconcile UOM, money, payment-method, and warehouse line fields per signed decisions (Priority: P2)

When a line is prepared for ERPNext, the connector MUST reconcile the DP2 free-text `unit` to an
ERPNext UOM per the **signed UOM decision** (`docs/decisions/mapping-uom.md`, Option A:
connector-side unit→ERPNext-UOM map; unmapped units fail closed), MUST treat money as
exact-decimal + ISO-4217 currency (never float), MUST apply the pre-resolved warehouse identity
(rider R5; never guessed), and MUST map payment method per the signed posting decision when the
Payment-Entry sub-scope is in force (gated; see §R1 / follow-up-notes.md). This spec records the
*policy* for these fields; it implements no posting.

**Why this priority**: Lower than the gating posting/idempotency/failure trio because these reuse
already-signed decisions rather than opening new ones. Documenting them here keeps implementation
from re-litigating them. The Payment-Entry / payment-method portion is gated by rider R1 and is NOT
in the first interim slice.

**Independent Test**: Reviewable as policy: the spec references `docs/decisions/mapping-uom.md`
(Option A) for unit handling, states money is exact-decimal + currency code, states the warehouse
is the DP2-pre-resolved identity (never guessed, rider R5), and defers payment-method mapping +
Payment Entry to the R1-gated sub-scope. An unmapped unit produces a fail-closed
`permanently_rejected` / `validation` outcome (US3), never a silent default.

**Acceptance Scenarios**:

1. **Given** a line with a DP2 free-text `unit`, **When** the connector maps it, **Then** it
   applies the signed connector-side unit→ERPNext-UOM map; an unmapped unit fails closed as
   `permanently_rejected` / `validation`, never a silent default.
2. **Given** a line amount, **When** the connector represents money, **Then** it uses the
   exact-decimal string + ISO-4217 currency form from the 012 contract, never a float.
3. **Given** the interim mode (rider R1), **When** the connector posts, **Then** it creates a
   submitted Sales Invoice only (outstanding AR) and does NOT create a Payment Entry — that is the
   gated sub-scope, not this slice.

---

### Edge Cases

- **Line with `tenantProductRef == null` (ad-hoc) on an OFFERED work-item**: by rider R2/R4 it
  cannot be offered without a resolved `erpnextItemRef` (it would have failed-to-DLQ in DP2). If the
  connector ever observes an offered line lacking `erpnextItemRef`, that is a **contract violation
  upstream** → treat as fail-closed (`permanently_rejected` / `validation`) and STOP-and-raise; do
  NOT substitute a "Misc" item (rider R3).
- **Re-offer after a prior `failed_transient`**: the connector posts idempotently — same
  `sourceSystem`+`externalId` → same ERPNext document, no duplicate (US2). The connector does not
  self-retry; the re-offer decision is DP2's (017).
- **Re-offer after a prior `permanently_rejected` (e.g. closed period later reopened, mapping later
  confirmed)**: an earlier permanent rejection does NOT, by itself, block a later successful post on
  a DP2 re-offer; the post is idempotent (US2).
- **Disabled / non-sales ERPNext Item at posting time**: per rider R3, DP2 fails the work-item to
  DLQ before offer (operational sellability stays DP2-authoritative). If the connector nonetheless
  hits ERPNext rejecting a disabled Item at submit, it surfaces `permanently_rejected` (US3) — never
  a silent substitute.
- **Missing DP-014 warehouse mapping**: per rider R5, fails-to-DLQ in DP2 before offer
  (`unmapped_store`-class). The connector never guesses the ERPNext warehouse.
- **Payment Entry attempted before the R1 gate clears**: forbidden — deriving a Payment Entry from
  `posTotal` (fabricated tender) is a STOP-and-raise (rider R1, "Not ratified").

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The connector MUST create an ERPNext sales document from each pulled posting
  work-item by **applying** the per-line pre-resolved `erpnextItemRef` (`{doctype:"Item", name}`)
  carried on the 012 posting-feed work-item. It MUST NOT resolve, look up, infer, reach back into
  DP2 for, or cache item identity (rider R2; `Q-CON-004` supersession of connector 004 FR-001).
- **FR-002**: The connector MUST address every ERPNext document **generically** as
  `{doctype, name}` (Item, Customer, Warehouse, the created Sales Invoice / Payment Entry) and MUST
  NOT fork ERPNext or copy a field-level ERPNext model (connector 004 FR-002, Principle II).
- **FR-003**: The connector MUST NOT perform item resolution, build/call DP2's suggest/confirm/
  retire review surface (`cookieAuth`), invent an auto-match source (`AUTO_MATCH_NO_SOURCE`), or
  create/search ERPNext Items. Item identity arrives pre-resolved on the work-item
  (rider R2/R3/R4; `Q-CON-004` retires connector 004 FR-001/FR-003 and the item-identity branch of
  its FR-006/US3). Connector 004 **FR-005** (no item-search / no Item-creation / no auto-match
  source) is **retained and reinforced** by this rescope, not retired — its prohibitions are carried
  forward here.
- **FR-004**: The first accepted posting model is the **signed target** "submitted Sales Invoice +
  associated Payment Entry" (rider R1). The **first implementation slice** posts the **interim
  "submitted Sales Invoice / outstanding-AR only"** mode (rider R1): Payment Entry is deferred and
  **gated** on (a) a DP2 tender/payment fact model, (b) a 012 payment-carrying extension, (c)
  idempotent Payment-Entry support, (d) payment repair/reconciliation semantics. The interim mode
  is explicitly **not finance-complete** and is expected to leave outstanding AR.
- **FR-005**: Every post MUST be **idempotent**, keyed on the DP2 `sourceSystem` + `externalId`
  (012 wire idempotency anchor, O-3): replaying the same logical sale MUST NOT create a duplicate
  ERPNext document, and an idempotent duplicate `posted` ack MUST echo the existing `documentRef`
  unchanged. The connector MUST NOT introduce a new idempotency primitive beyond the 012 contract
  (Principle IV / Gate G5).
- **FR-006**: A posting failure MUST be reported as a typed `connectorAckOutcome` outcome —
  `failed_transient` (retryable; DP2 re-offers) or `permanently_rejected` (carries a structured
  `reason`) — and MUST NOT create a partial document, guess, or silently drop the work-item
  (Principle VI). The connector MUST NOT invent a connector-side retry loop; DP2 owns DLQ + 017
  reconciliation.
- **FR-007**: The `permanently_rejected` reason MUST be reported through the existing 012
  `RejectionReason` taxonomy, drawing `reason.category` from DP2's **closed** set
  (`validation | closed_period | unmapped_item | unmapped_account | other`) — **no new wire reason
  invented**. Reporting MUST NOT mutate the original DP2 sale fact (012 O-3 / Principle IV).
- **FR-008**: The connector MUST reconcile a line's DP2 free-text `unit` to an ERPNext UOM per the
  **signed UOM decision** (`docs/decisions/mapping-uom.md`, Option A: connector-side
  unit→ERPNext-UOM map). An unmapped unit MUST fail closed as `permanently_rejected` with
  `reason.category = validation` (there is no `unmapped_uom` category; an unmapped unit is a
  line-validation failure), never a silent default (Principle VI; connector 004 FR-008 retained).
- **FR-009**: The connector MUST represent every monetary value as an exact-decimal string paired
  with an ISO-4217 currency code (never a float), consistent with the 012 contract's
  `DecimalAmount` + `CurrencyCode` shapes (connector 004 FR-009 retained).
- **FR-010**: The connector MUST apply the **DP2-pre-resolved warehouse / store identity** for
  stock-affecting postings (rider R5) and MUST NOT guess the ERPNext warehouse. A missing DP-014
  warehouse mapping fails-to-DLQ in DP2 before offer; an offered work-item carries a resolved
  warehouse identity the connector applies generically (FR-002).
- **FR-011**: A failed posting MUST be **repairable without modifying the original DP2 sale fact**
  (constitution Principle IV; README 006 exit criterion). The connector does not self-mutate the
  source sale; repair is a DP2-driven re-offer.
- **FR-012**: Every posting outcome (success or failure) MUST be **observable** and traceable
  end-to-end via the DP2 correlation id (`request_id`, spec 003 substrate), with a typed error
  taxonomy, retry status, and structured logs, and MUST NOT expose secrets/tokens/credentials in
  logs, errors, or UI (Principle V / Gate G4 / G7).
- **FR-013**: Every Data-Pulse-2 reference in this spec and its companion docs MUST cite a real
  path in the Data-Pulse-2 repository (verified to locate and confirm the claim); the connector
  MUST NOT re-derive DP2's model (Principle I, `dp2-citation-verification`).
- **FR-014**: The connector's posting poller MUST be introduced as a Frappe **`scheduler_event`**
  registered in `hooks.py` — but **NOT in this planning slice**. `hooks.py` stays empty at this
  layer (spec 001 FR-005); the registration is a *planned* downstream implementation task recorded
  in [follow-up-notes.md](./follow-up-notes.md) (Principle VII; Gate G8 lands on the runtime).
- **FR-015**: The connector MUST NOT author or modify any OpenAPI contract. The 012 posting-feed
  contract (`packages/contracts/openapi/erpnext-connector/posting-feed.yaml`, owned by DP2,
  `1.1.0-draft`) is the authoritative wire surface; the connector consumes it (FR-013, Principle I).

### Key Entities *(include if feature involves data)*

- **Posting work-item** (`PostingWorkItem`, 012 posting-feed): the unit the connector PULLs over
  `connectorPullPostings` — a frozen 008 sale projection (header + lines), its `sourceSystem` +
  `externalId` + `payloadHash` provenance, and (per line) the DP2-resolved `erpnextItemRef`. The
  connector's input; not owned by the connector.
- **Resolved ERPNext Item reference** (`ErpnextItemRef`, 012): a `{doctype:"Item", name}` generic
  address, `name` = the 013 `erpnext_item_ref` string. **Pre-resolved DP2-side**; the connector
  APPLIES it (never resolves it). The supersession boundary of `Q-CON-004` / rider R2.
- **ERPNext sales document**: the output — an interim submitted **Sales Invoice** (signed target:
  Sales Invoice + Payment Entry, gated by rider R1). Addressed generically `{doctype, name}`; its
  `documentRef` is returned to DP2.
- **Posting outcome** (`OutcomeAckRequest` / `RejectionReason`, 012): a typed
  `posted | failed_transient | permanently_rejected` ack over `connectorAckOutcome`; `posted`
  carries `documentRef`, `permanently_rejected` carries a `reason.category` from the closed set.
  Drives DP2's 017 reconciliation; never a silent default. The re-offer decision is DP2's.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can trace every posting work-item to a documented posting path that ends
  in exactly one typed outcome — `posted` (one submitted ERPNext document, `documentRef` returned)
  XOR `failed_transient` XOR `permanently_rejected` — with **zero** silent partials, guesses, or
  dropped work-items.
- **SC-002**: 100% of DP2 references in the spec and its companion docs resolve to a real
  Data-Pulse-2 repository path and confirm the claim made (no phantom citations).
- **SC-003**: The spec documents the **apply-only** item-identity posture (the connector applies
  the pre-resolved `erpnextItemRef` and performs NO resolution/lookup/cache) — and a reviewer
  confirms no connector-side item-resolution, item-search, item-creation, or DP2-reachback path
  appears anywhere (rider R2/R3/R4; `Q-CON-004`).
- **SC-004**: Replay is provably duplicate-free at the policy level: the spec states the
  `sourceSystem`+`externalId` replay key, the same-document-on-re-offer rule, and the
  ack-replay / `409 idempotency_key_conflict` rule — with no new idempotency primitive (Gate G5).
- **SC-005**: Every failure is reported at the outcome level with a `reason.category` from DP2's
  **existing closed set** and **no new wire reason code is invented**; the original DP2 sale fact is
  never mutated (FR-007 / FR-011).
- **SC-006**: The Payment-Entry sub-scope is explicitly **gated** (rider R1) and the first slice's
  interim "submitted Sales Invoice / outstanding-AR only" posture is documented as **not
  finance-complete** before any posting code is written.
- **SC-007**: `hooks.py` remains unedited by this slice; the poller `scheduler_event` is recorded
  as a *planned* downstream task (FR-014). No connector code, no OpenAPI, no migration is produced.
- **SC-008** *(deferred — bench)*: On a staging ERPNext v15 site, a posting work-item with resolved
  lines posts to a submitted Sales Invoice and returns its `documentRef`; a re-offer of the same
  sale returns the SAME `documentRef` (no duplicate); a transient failure acks `failed_transient`.
  Marked ⏳ BENCH-VALIDATION; not claimed until run on a real bench (standing-rules §6).

## Assumptions

- **Item identity arrives pre-resolved (rider R2 / `Q-CON-004`).** DP2 resolves each line's ERPNext
  Item at work-item projection (confirmed 013 mapping) and offers a self-sufficient work-item
  carrying `erpnextItemRef`; unresolvable lines fail-to-DLQ in DP2 before offer. The connector
  applies, never resolves. This supersedes connector 004's connector-side-resolution framing.
- **The 012 posting-feed contract is fixed and DP2-owned** (`1.1.0-draft`, carries the required
  `erpnextItemRef`). This spec cites it; it authors no OpenAPI (FR-015, Principle I).
- **The first slice is the interim invoice-only / outstanding-AR mode** (rider R1). Payment Entry is
  gated; the signed target (SI + PE) is unchanged.
- **The signed UOM decision (Option A) applies** to unit reconciliation
  (`docs/decisions/mapping-uom.md`); no new unit decision is opened here.
- **The spec-003 auth + idempotency + correlation + error policy is the substrate**
  (`docs/decisions/data-pulse-auth-and-api-policy.md`): the connector authenticates TO DP2 (client;
  DP2 makes no outbound calls), reuses `connectorAckOutcome`'s taxonomy, the DP2 `request_id`
  correlation, and the secrets discipline.
- **No connector code, no `hooks.py` edit, no migration in this spec.** Like connector 004 and
  DP2's 015 spec, this is a planning/policy artifact. Implementation (poller registration, posting
  worker, idempotency store, UOM map) lands in later slices and is bench-validated then.

## Dependencies

- **DP-015 sale-posting spec** (`Data-Pulse-2/specs/015-pos-sale-posting-to-erpnext/`) + signed
  rider `011-DR-POSTING-R1` — the authoritative posting model, item-resolution side (R2), failure
  postures (R3/R4/R5), and Payment-Entry gating (R1). Cited, not re-derived.
- **012 posting-feed contract** (`Data-Pulse-2/packages/contracts/openapi/erpnext-connector/
  posting-feed.yaml`, `1.1.0-draft`) — the wire surface: `connectorPullPostings` /
  `connectorAckOutcome`, `PostingWorkItem` / `SaleLine` (required `erpnextItemRef`), the outcome
  enum + `RejectionReason` closed set, `DecimalAmount` / `CurrencyCode`, the O-3 idempotency
  anchor. Read-only input; the authoritative item-identity carrier.
- **Connector spec 004** (`specs/004-product-erpnext-item-mapping/`) — rescoped by `Q-CON-004`:
  this spec **inherits** its retained FR-002 (generic addressing) + FR-008/US4 (UOM + money) and
  **does not** inherit its retired FR-001/FR-003 (connector-side resolution).
- **Connector spec 003** (`docs/decisions/data-pulse-auth-and-api-policy.md`) — auth / idempotency
  / error taxonomy / correlation / secrets substrate for FR-005/006/007/011/012.
- **Signed UOM decision** (`docs/decisions/mapping-uom.md`, Option A) — input to FR-008.
- **Inherited implementation gates (NOT satisfied here)**: DP-014 warehouse mapping (rider R5),
  `P-DP-008-LIVELOOP` (e2e live-loop), the rest of the DP-015 Spec-Kit implementation chain, and
  connector gates G5 (idempotency) / G7 (observability) / G8 (upgrade) / G9 (pilot). See
  [follow-up-notes.md](./follow-up-notes.md).
