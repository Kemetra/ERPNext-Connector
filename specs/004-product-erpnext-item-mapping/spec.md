# Feature Specification: Product–ERPNext Item Mapping (Posting Resolution)

**Feature Branch**: `004-004-product-erpnext`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "004 Product and Price Export" (README roadmap item) — **reframed**
on 2026-06-04 (signed Option A) after surveying the authoritative Data-Pulse-2 contracts. The
README framing ("Data-Pulse builds a canonical catalog FROM ERPNext data" — Item/Barcode/UOM/
Price-List export) has **no viable contract path** in DP2 today and conflicts with the
constitution. This spec instead defines the connector's *actual* catalog responsibility: the
**DP2-product → ERPNext-Item identity mapping** that lets a sale-line resolve to a real ERPNext
Item at posting time. Authoritative references (read-only):
`packages/contracts/openapi/catalog/erpnext-item-map.yaml` (DP2 spec 013, migration 0017) and
`packages/contracts/openapi/erpnext-connector/posting-feed.yaml` (the `tenantProductRef` field).
This is a policy/contract-alignment spec — cite DP2, do not re-derive; honor constitution
Principles I, VI, VII and quality gate G1.

## Clarifications

### Session 2026-06-04

- Q: Does spec 004 export product/price data FROM ERPNext to Data-Pulse-2 (the README framing)?
  → A: **No.** No DP2 contract supports it and the reverse direction is constitutionally barred.
  Evidence from the real DP2 repo: (1) the only `connectorBearer` machine surface,
  `posting-feed.yaml`, has exactly two operations — `connectorPullPostings` and
  `connectorAckOutcome` — and **no** product/price/item-export or catalog-push operation;
  (2) DP2 documents the absence explicitly (`AUTO_MATCH_NO_SOURCE`: "no ERPNext item-search op
  exists in the 012 connector contract"; OQ-8 "forbids an import worker"); (3) DP2 is the
  **catalog authority** — `catalog/read-down.yaml` (spec 010) and `catalog/erpnext-item-map.yaml`
  (spec 013) both state "003 Tenant Catalog stays authoritative; ERPNext owns accounting-Item
  identity only", and the POS catalog flows DP2 → POS from DP2's own `tenant_products`, not from
  ERPNext; (4) the reverse direction (DP2 pulling a connector-exposed product API) is barred by
  the ratified Gate-G4 clarification (constitution v1.0.1: "the connector is the client; DP2 makes
  no outbound calls"). (See Assumptions.)
- Q: What IS the connector's catalog responsibility, then? → A: **Map the DP2 tenant-product
  reference on each sale line to an ERPNext Item so postings resolve.** `posting-feed.yaml`
  (line 481–484) carries `tenantProductRef` on each sale line and states "The connector maps it
  to an ERPNext Item (013) behind this contract." DP2 spec 013 holds the
  suggest→confirm→retire mapping lifecycle; **only `confirmed` mappings resolve at posting time**
  (the confirmed-only invariant). This spec defines how the connector *consumes* that confirmed
  mapping and how it behaves when a line is unmapped/unconfirmed (Principle VI — surface, never
  silently guess). It does NOT define a catalog export.
- Q: Who owns the suggest/confirm review surface? → A: **Data-Pulse-2 (Retail-Tower-Console),
  not the connector.** The `erpnext-item-map.yaml` operations are `cookieAuth` (human Tenant-Admin
  via the dashboard session), explicitly **not** the `connectorBearer` machine scheme. The
  connector neither builds nor calls that review UI; it consumes the *confirmed* mapping's effect
  at posting time. This keeps Principle I intact (DP2 is the only orchestration boundary).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve a sale-line's product to an ERPNext Item at posting time (Priority: P1)

When the connector pulls a posting work-item from Data-Pulse-2, each sale line carries an
optional `tenantProductRef` (a DP2 tenant-product UUID). To post a Sales Invoice line to ERPNext,
the connector MUST resolve that reference to a concrete ERPNext **Item** using the *confirmed*
DP2-product → ERPNext-Item mapping (DP2 spec 013), addressing ERPNext generically as
`{doctype: "Item", name: <erpnext_item_ref>}` — never via a forked/field-level ERPNext model.

**Why this priority**: This is the catalog half of sales posting (spec 006). A posting work-item
cannot become an ERPNext Sales Invoice line until its product reference resolves to a real Item.
Defining the resolution policy now — before any posting code — is exactly the contract-first gate
(Principle VII) and de-risks 006. It is the minimum viable catalog capability.

**Independent Test**: Reviewable as policy: given a posting work-item whose sale line carries a
`tenantProductRef` that has a *confirmed* mapping, the documented resolution path produces a
single ERPNext Item reference; the path cites the DP2 contracts and addresses ERPNext generically.

**Acceptance Scenarios**:

1. **Given** a sale line with a `tenantProductRef` that has a **confirmed** `erpnext_item_map`
   entry, **When** the connector resolves the line, **Then** it yields exactly one ERPNext Item
   reference (the mapping's `erpnext_item_ref`), addressed as a generic `{doctype, name}`.
2. **Given** a sale line whose `tenantProductRef` is **null** (an ad-hoc line, per
   `posting-feed.yaml`), **When** the connector resolves the line, **Then** the documented policy
   states how an ad-hoc/unreferenced line is handled (it is not silently dropped — see US3).
3. **Given** ERPNext, **When** the connector references an Item, **Then** it uses the generic
   `{doctype: "Item", name}` form (Principle II), never a copied ERPNext field model.

---

### User Story 2 - Honor the confirmed-only invariant and mapping lifecycle (Priority: P2)

The connector MUST treat only **confirmed** mappings as resolvable. A mapping in `suggested`
state, or a `retired` mapping, MUST NOT resolve a sale line. The connector consumes the lifecycle
defined in DP2 spec 013 (suggest → confirm → retire, append-only, optimistic-concurrency
`version`) — it does not re-implement or bypass it.

**Why this priority**: Resolving against an unconfirmed or retired mapping would post a sale line
to the wrong (or an unreviewed) ERPNext Item — a silent fiscal error. The confirmed-only
invariant (DP2 data-model §3) is the safety boundary; documenting that the connector honors it is
what keeps Principle VI (truth never hidden) intact. Depends on US1's resolution path.

**Independent Test**: Reviewable as policy: the spec states that `state != confirmed` (or
`retired_at != null`) is treated as *not resolvable* and routed to the unresolved path (US3),
never resolved optimistically.

**Acceptance Scenarios**:

1. **Given** a `tenantProductRef` whose only mapping is in `suggested` state, **When** resolution
   runs, **Then** the line is treated as **unresolved** (US3), not posted against the suggestion.
2. **Given** a `tenantProductRef` whose mapping was `retired`, **When** resolution runs, **Then**
   the line is treated as **unresolved**, not posted against the retired identity.
3. **Given** the mapping lifecycle, **When** the connector references it, **Then** the spec cites
   DP2 spec 013's suggest/confirm/retire model and asserts the connector neither calls the
   tenant-admin review surface (`cookieAuth`) nor invents an auto-match source
   (`AUTO_MATCH_NO_SOURCE`).

---

### User Story 3 - Surface unresolved products explicitly, never silently (Priority: P1)

When a sale line cannot be resolved to a confirmed ERPNext Item (no mapping, suggested-only,
retired, or ad-hoc with no reference), the connector MUST surface that as an explicit, typed
unresolved outcome — fail closed — and MUST NOT guess an Item, drop the line, or post a partial
invoice. The unresolved outcome MUST be expressible through the connector's existing
`connectorAckOutcome` rejection vocabulary (spec 003) so Data-Pulse-2 sees the gap.

**Why this priority**: Co-equal P1 with US1. The constitution's Principle VI ("fiscal & stock
truth is never hidden") makes the *unhappy path* a first-class requirement, not an afterthought:
an unmapped product must be visible to DP2 for reconciliation, exactly as DP2 surfaces unpriced
products to "an observability signal + reconciliation backlog" rather than silently. Without this,
a missing mapping becomes a silent posting failure or a wrong post.

**Independent Test**: Reviewable as policy: the spec reports every unresolved case as a
`permanently_rejected` `connectorAckOutcome` with a `reason.category` from DP2's closed set
(`unmapped_item` for product cases, `validation` for an unmapped UOM), and forbids silent
default/guess/drop.

**Acceptance Scenarios**:

1. **Given** a sale line whose `tenantProductRef` has **no** active mapping, **When** resolution
   runs, **Then** the connector acks `permanently_rejected` with `reason.category = unmapped_item`
   via `connectorAckOutcome`, and posts nothing for that work-item until the mapping is confirmed.
2. **Given** an unresolved line, **When** the outcome is reported, **Then** no ERPNext Item is
   guessed and the original DP2 sale fact is not mutated (Principle IV / DP2 O-3).
3. **Given** the unresolved outcome, **When** an operator inspects it, **Then** it is traceable to
   the work-item and the `tenantProductRef` via the spec-003 correlation policy (DP2 `request_id`),
   with no secret/token leaked (Gate G4 / Principle V).

---

### User Story 4 - Reconcile UOM and money fields at the line, per signed decisions (Priority: P3)

When a resolved line is prepared for ERPNext, the connector MUST reconcile the DP2 free-text
`unit` to an ERPNext UOM per the **signed UOM decision** (Option A: connector-side
unit→ERPNext-UOM map; unmapped units fail closed), and MUST treat money as exact-decimal +
ISO-4217 currency (never float), as DP2's contracts require. This spec records the *policy* for
these line fields; it does not implement posting (spec 006).

**Why this priority**: Lower priority because identity resolution (US1–US3) is the gating concern;
unit/money reconciliation is the next layer and reuses an already-signed decision rather than
opening a new one. Documenting it here keeps 006 from re-litigating it.

**Independent Test**: Reviewable as policy: the spec references `docs/decisions/mapping-uom.md`
(Option A) for unit handling and states money is carried as exact-decimal + currency code, with an
unmapped unit producing the same fail-closed unresolved outcome as an unmapped product (US3).

**Acceptance Scenarios**:

1. **Given** a resolved line with a DP2 free-text `unit`, **When** the connector maps it, **Then**
   it applies the signed connector-side unit→ERPNext-UOM map; an **unmapped** unit fails closed as
   `permanently_rejected` with `reason.category = validation`, never a silent default.
2. **Given** a line amount, **When** the connector represents money, **Then** it uses the
   exact-decimal string + ISO-4217 currency form from the DP2 contracts, never a float.

---

### Edge Cases

- **Ad-hoc line (`tenantProductRef == null`)**: `posting-feed.yaml` allows null for ad-hoc lines.
  The policy MUST state explicitly whether an ad-hoc line is (a) routed to the unresolved path, or
  (b) posted against a configured fallback/"miscellaneous" Item — and if (b), the fallback MUST be
  an explicit, configured decision, never an implicit guess. *(Candidate decision record.)*
- **More than one active mapping for a product**: DP2 enforces at most one active mapping per
  `tenant_product_id` (OQ-2 1:1, `409 conflict` on a second active suggestion). The connector
  relies on this invariant; if it ever observes two confirmed mappings it MUST treat the state as
  unresolved (fail closed), not pick one.
- **Mapping confirmed after a prior `unmapped_item` ack**: if DP2 re-offers the same work-item
  after the mapping is confirmed, the connector MUST resolve and post idempotently (Principle IV;
  same `sourceSystem`+`externalId` → same ERP doc, no duplicate). The earlier `unmapped_item` ack
  does not, by itself, block a later successful post. (The re-offer decision is DP2's, via its 017
  reconciliation; the connector does not self-retry.)
- **Stale/version-skewed mapping**: the connector does not mutate mappings (no `version` it owns);
  it reads the *currently confirmed* mapping at resolution time. The spec states resolution uses
  the confirmed mapping as-of-posting, with no connector-side caching that could resolve a retired
  identity.
- **ERPNext Item missing despite a confirmed mapping**: a confirmed `erpnext_item_ref` whose Item
  does not exist in ERPNext is an unresolved outcome (fail closed), not a created Item — the
  connector never creates catalog masters (no import worker; OQ-8).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The connector MUST resolve each posting work-item sale line's `tenantProductRef`
  (DP2 tenant-product UUID, per `posting-feed.yaml`) to an ERPNext Item using the **confirmed**
  DP2-product → ERPNext-Item mapping defined in DP2 spec 013
  (`catalog/erpnext-item-map.yaml`, migration 0017).
- **FR-002**: The connector MUST address the resolved ERPNext Item **generically** as
  `{doctype: "Item", name: <erpnext_item_ref>}` and MUST NOT fork ERPNext or copy a field-level
  ERPNext Item model (Principle II).
- **FR-003**: The connector MUST treat **only** mappings in `state = confirmed` (and
  `retired_at = null`) as resolvable. `suggested` and `retired` mappings MUST NOT resolve a line
  (the confirmed-only invariant, DP2 data-model §3).
- **FR-004**: The connector MUST NOT call or re-implement DP2's suggest/confirm/retire review
  surface — those operations are `cookieAuth` (human Tenant-Admin via Retail-Tower-Console),
  explicitly not the `connectorBearer` machine scheme. The connector consumes only the *effect* of
  a confirmed mapping at posting time (Principle I).
- **FR-005**: The connector MUST NOT invent an auto-match source for mappings. DP2 records
  `AUTO_MATCH_NO_SOURCE` (no ERPNext item-search op in the connector contract) and forbids an
  import worker (OQ-8); the connector MUST NOT create ERPNext Items, search ERPNext for matches,
  or otherwise act as a catalog import path.
- **FR-006**: When a sale line cannot be resolved to a confirmed Item (no active mapping,
  suggested-only, retired, ad-hoc with no reference, or confirmed-but-Item-absent), the connector
  MUST report `outcome = permanently_rejected` with `reason.category = unmapped_item` and fail
  closed — it MUST NOT guess an Item, post a partial invoice, or silently drop the line
  (Principle VI). It MUST NOT invent a connector-side retry; DP2 owns the dead-letter +
  reconciliation flag (DP2 spec 017) that follows a `permanently_rejected` outcome.
- **FR-007**: The unresolved outcome MUST be reported to Data-Pulse-2 through the existing
  `connectorAckOutcome` `RejectionReason` taxonomy (spec 003 / `posting-feed.yaml`), drawing
  `reason.category` from DP2's **closed** set (`validation | closed_period | unmapped_item |
  unmapped_account | other`) — no new wire reason invented. Reporting MUST NOT mutate the original
  DP2 sale fact (DP2 O-3 / Principle IV).
- **FR-008**: The connector MUST reconcile a resolved line's DP2 free-text `unit` to an ERPNext
  UOM per the **signed UOM decision** (`docs/decisions/mapping-uom.md`, Option A: connector-side
  unit→ERPNext-UOM map). An **unmapped** unit MUST fail closed as `permanently_rejected`, but with
  `reason.category = validation` (there is no `unmapped_uom` category in DP2's closed set; an
  unmapped unit is a line-validation failure, NOT an `unmapped_item`), never a silent default
  (Principle VI).
- **FR-009**: The connector MUST represent every monetary value as an exact-decimal string paired
  with an ISO-4217 currency code (never a float), consistent with the DP2 contracts'
  `DecimalAmount` + `CurrencyCode` shapes.
- **FR-010**: Resolution MUST be **replay-safe**: **when** DP2 re-offers a work-item (the decision
  to re-offer is DP2's — it owns the DLQ + 017 reconciliation, not the connector), re-processing it
  MUST resolve and post idempotently — the same `sourceSystem` + `externalId` MUST map to the same
  ERPNext document, never a duplicate (Principle IV / DP2 O-3). An earlier `unmapped_item` ack MUST
  NOT, by itself, prevent a later successful post once the mapping is confirmed.
- **FR-011**: An unresolved or resolution-error outcome MUST be traceable end-to-end via the
  spec-003 correlation policy (DP2 `request_id`) and MUST NOT expose secrets, tokens, or
  credentials in logs, errors, or UI (Gate G4 / Principle V).
- **FR-012**: The connector MUST decide the **ad-hoc line policy** explicitly (route to unresolved
  vs. configured fallback Item). The default is fail-closed (route to unresolved); any fallback
  MUST be a configured, signed decision — never an implicit guess. *(Recorded as a candidate
  decision; see Assumptions/Dependencies.)*
- **FR-013**: Every DP2 reference in this spec and its decision records MUST cite a real path in
  the Data-Pulse-2 repository (verified to locate and confirm the claim); the connector MUST NOT
  re-derive DP2's model (Principle I, `dp2-citation-verification`).

### Key Entities *(include if feature involves data)*

- **Sale-line product reference (`tenantProductRef`)**: a nullable DP2 tenant-product UUID on each
  posting work-item sale line (`posting-feed.yaml`). Null = ad-hoc line. The connector's input to
  resolution; it is *not* owned by the connector.
- **ERPNext Item mapping (`erpnext_item_map`)**: the DP2-side identity mapping (DP2 spec 013,
  migration 0017): `tenant_product_id` → `erpnext_item_ref` (opaque ERPNext Item code/name), with
  lifecycle `state ∈ {suggested, confirmed}`, append-only retire (`retired_at`), and an
  optimistic-concurrency `version`. The connector reads only the **confirmed, non-retired** row.
- **ERPNext Item reference**: the resolution output — a generic `{doctype: "Item", name}` address
  (Principle II). Carries no copied ERPNext field model.
- **Unresolved outcome**: a `permanently_rejected` `connectorAckOutcome` (spec 003 /
  `posting-feed.yaml`) carrying a structured `reason.category` from DP2's closed set — `unmapped_item`
  for an unresolved product (no confirmed Item, suggested-only, retired, or Item-absent) and
  `validation` for an unmapped UOM. Visible to DP2 for dead-letter + reconciliation (017); never a
  silent default. The decision to re-offer the work-item is DP2's, not the connector's.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can trace every sale-line product reference in a posting work-item to a
  documented resolution path that ends in either a single confirmed ERPNext Item or a typed
  unresolved outcome — with **zero** silent guesses or dropped lines.
- **SC-002**: 100% of DP2 references in the spec and its decision records resolve to a real
  Data-Pulse-2 repository path and confirm the claim made (no phantom citations).
- **SC-003**: Every unresolved case is reported at the outcome level as `permanently_rejected`
  (uniform), with its `reason.category` drawn from DP2's **existing closed set** — `unmapped_item`
  for product cases, `validation` for an unmapped UOM — and **no new wire reason code is invented**
  (the connector maps its internal reasons onto the existing taxonomy).
- **SC-004**: A reviewer confirms the connector neither calls DP2's tenant-admin review surface
  (`cookieAuth`) nor creates/searches ERPNext Items — i.e. no catalog-import or item-search path
  appears anywhere in the spec (Principle I/II, `AUTO_MATCH_NO_SOURCE`, OQ-8).
- **SC-005**: The ad-hoc line policy is explicit and signed (fail-closed default; any fallback Item
  recorded as a signed decision) before spec 006 (sales posting) implements line resolution.
- **SC-006** *(deferred — bench)*: On a staging ERPNext v15 site, a posting work-item with a
  confirmed mapping resolves to its Item, and a work-item with no confirmed mapping acks
  `permanently_rejected` / `unmapped_item` — idempotent on a DP2 re-offer. Marked
  ⏳ BENCH-VALIDATION; not claimed until run on a real bench (standing-rules §6).

## Assumptions

- **DP2 is the catalog authority; ERPNext owns accounting-Item identity only.** This spec does not
  export product/price data from ERPNext to DP2 (no such DP2 contract exists; the reverse direction
  is barred by Gate G4). DP2's Tenant Catalog (spec 003) and POS read-down (spec 010) remain the
  catalog source.
- **The mapping lifecycle is owned by DP2 (spec 013).** Suggest/confirm/retire is a human
  Tenant-Admin action in Retail-Tower-Console via `cookieAuth`. The connector consumes only the
  confirmed mapping's effect at posting time and never the review surface.
- **The signed UOM decision (Option A) applies** to unit reconciliation
  (`docs/decisions/mapping-uom.md`): connector-side unit→ERPNext-UOM map, unmapped fails closed.
  No new unit decision is opened here.
- **The spec-003 auth + idempotency + correlation + error policy is the substrate.** This spec
  reuses `connectorAckOutcome`'s rejection vocabulary, the DP2 `request_id` correlation, and the
  secrets discipline rather than defining new transport policy.
- **No connector code in this spec.** Like 002 and 003, this is a policy/contract-alignment
  artifact (docs + decision records). Implementation (resolution code, the unit→UOM map, posting)
  lands in later specs (006) and is bench-validated then.

## Dependencies

- **DP2 spec 013 `erpnext_item_map`** (`catalog/erpnext-item-map.yaml`, migration 0017) and the
  `posting-feed.yaml` `tenantProductRef` field — the authoritative inputs. Read-only; cited, not
  re-derived.
- **Confirmed mappings must actually exist in DP2 at posting time.** Resolution depends on a
  Tenant Admin having confirmed each product's mapping in Retail-Tower-Console. Until a product is
  confirmed, its lines are unresolved (FR-006) — this is a DP2-side data-readiness dependency,
  tracked outside this spec's slice graph (analogous to the spec-003 token-scope dependency).
- **Signed UOM decision** (`docs/decisions/mapping-uom.md`, Option A) — input to FR-008.
- **Spec 003 policy** (auth, idempotency, error taxonomy, correlation, secrets) — substrate for
  FR-007/FR-010/FR-011.
- **Candidate decision: ad-hoc line policy** (FR-012) — must be signed before spec 006 line
  resolution.
