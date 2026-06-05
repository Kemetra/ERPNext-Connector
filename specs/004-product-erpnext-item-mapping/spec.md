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
- Q: How should the connector handle an ad-hoc sale line (`tenantProductRef == null`) — fail closed
  or post against a configured fallback Item? → A: **Fail closed (Option A, signed 2026-06-04).** An
  ad-hoc line is reported `permanently_rejected` with `reason.category = unmapped_item`, identical to
  any other unresolved product — no configured catch-all/"miscellaneous" Item. Rationale: Principle
  VI (surface, never silently absorb); a catch-all Item would distort ERPNext item-level reporting
  and could mask a real catalog gap. A fallback Item remains a *future* explicit signed opt-in if a
  concrete POS ad-hoc-line need appears; it is not the default. FR-012 is no longer an open decision.

### Session 2026-06-05 (Q-CON-004 rescope-with-supersession)

- Q: Does the connector itself resolve a sale line's `tenantProductRef` to an ERPNext Item
  (the original US1/FR-001 connector-side resolution)? → A: **No — retired.** The ratified
  **Q-CON-004 rescope** (Wave A, 2026-06-05) and the signed owner rider
  **`011-DR-POSTING-R1 §R2`** (Data-Pulse-2 repo,
  `specs/011-erpnext-pos-reference-and-integration-foundation/decisions/posting-decision-rider-2026-06-05.md`)
  ratify **DP2-side item resolution at work-item projection time**: DP2 resolves each sale
  line against the 013 `erpnext_item_map` (confirmed-only invariant) **before** the work-item
  is offered; a line that cannot resolve **fails-to-DLQ in DP2 before offer** and never reaches
  the connector. The connector therefore receives an already-resolved ERPNext Item reference on
  the work-item (the new DP-012 field `SaleLine.erpnextItemRef`, gated on **`P-DP-012-EXT`**) and
  **MUST NOT** guess Item identity, reach back into DP2 for item lookup, or maintain a second copy
  of DP2 mapping truth (rider §R2).
- Consequently, the **connector-side resolution mechanism is retired**: **FR-001** (connector
  resolves via the 013 map), **FR-003** (connector owns/enforces the confirmed-only invariant), and
  the **item-identity branch of FR-006 / US3** (connector deciding *unmapped_item* by inspecting
  mapping state) are marked `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2;
  ratified Q-CON-004. Preserved for history.]`. **US1** and **US2** (the user-story form of the
  retired FRs) carry the same marker. History is preserved (no deletion).
- **Retained subset** (the surviving connector responsibility, which **spec 006 inherits**):
  **FR-002** — generic `{doctype: "Item", name}` addressing of the *pre-resolved* `erpnextItemRef`
  (unmodified); **FR-008 / US4** — connector-side UOM reconciliation + exact-decimal/ISO-4217 money
  (unmodified); **FR-005** — no item-search / no Item-creation / no auto-match (retained and
  **reinforced**: rider §R2 makes the connector fully item-resolution-free). **FR-007** is retained
  because the UOM/`validation` branch of US3 (driven by FR-008) still reports through its
  `connectorAckOutcome` taxonomy.
- Scope note: **FR-010** (replay-safe idempotent posting) and **FR-012** (ad-hoc fail-closed) are
  **not** retired by this rescope; they are read in light of rider §R2 (resolution now happens
  DP2-side before offer) and are treated in **spec 006**. They are listed here only for reference,
  not marked retired.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve a sale-line's product to an ERPNext Item at posting time (Priority: P1)

> `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]`
> Connector-side item resolution is retired: DP2 resolves the ERPNext Item at work-item
> projection time and offers the connector a pre-resolved `erpnextItemRef` (gated on
> `P-DP-012-EXT`). The connector no longer performs the resolution described below. Retained from
> this story: the connector still addresses ERPNext **generically** as `{doctype: "Item", name}`
> over the pre-resolved reference (FR-002, Acceptance Scenario 3). See Clarifications 2026-06-05.

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

> `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]`
> The confirmed-only invariant is now enforced **DP2-side** at projection time (rider §R2):
> unconfirmed/retired mappings fail-to-DLQ in DP2 before offer and never reach the connector. The
> connector no longer reads mapping state or owns this invariant. See Clarifications 2026-06-05.

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

> **Item-identity branch** `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]`
> The *product/item* unresolved branch of this story (no mapping / suggested-only / retired /
> ad-hoc / Item-absent → `unmapped_item`) is retired: per rider §R2 those cases **fail-to-DLQ in
> DP2 before offer**, so the connector never observes an item-unresolved line. **Retained:** the
> **UOM/`validation` branch** (an unmapped unit on an otherwise-resolved line) stays a live
> connector responsibility (FR-008 → reported via FR-007's `connectorAckOutcome` taxonomy), as does
> the fail-closed *reporting* discipline itself (FR-007). See Clarifications 2026-06-05.

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

1. ~~**Given** a sale line whose `tenantProductRef` has **no** active mapping, **When** resolution
   runs, **Then** the connector acks `permanently_rejected` with `reason.category = unmapped_item`
   via `connectorAckOutcome`, and posts nothing for that work-item until the mapping is confirmed.~~
   *(RETIRED §R2 — item-unresolved is now a DP2-side pre-offer fail-to-DLQ case; the connector never acks `unmapped_item`. Preserved for history.)*
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
unmapped unit producing the same fail-closed *outcome* as an unmapped product (`permanently_rejected`),
differing only in `reason.category` (`validation` for UOM vs. `unmapped_item` for product) (US3).

**Acceptance Scenarios**:

1. **Given** a resolved line with a DP2 free-text `unit`, **When** the connector maps it, **Then**
   it applies the signed connector-side unit→ERPNext-UOM map; an **unmapped** unit fails closed as
   `permanently_rejected` with `reason.category = validation`, never a silent default.
2. **Given** a line amount, **When** the connector represents money, **Then** it uses the
   exact-decimal string + ISO-4217 currency form from the DP2 contracts, never a float.

---

### Edge Cases

> **[RECONCILED 2026-06-05 — Q-CON-004 / rider 011-DR-POSTING-R1 §R2]** The four item-resolution edge cases below are **retired from the connector**: item resolution is DP2-side, and any line that cannot resolve (ad-hoc/null, multi-mapping, unconfirmed, retired, or Item-absent) **fails-to-DLQ in DP2 *before* the work-item is offered** — so the connector never observes these states on an offered line. They are preserved as the DP2-side pre-offer policy (informational here; owned by DP2 spec 013/015 + rider §R2/§R3/§R4). The **ad-hoc** and **UOM** policies remain relevant to the connector's retained scope (FR-002 apply-ref; FR-008/US4 UOM).
- **Ad-hoc line (`tenantProductRef == null`)**: `posting-feed.yaml` allows null for ad-hoc lines.
  **Signed policy: fail closed** — an ad-hoc line that cannot resolve to a confirmed Item fails-to-DLQ **DP2-side before offer** (rider §R3/§R4, no substitute/Misc Item); ~~the connector reports `permanently_rejected` / `unmapped_item`~~ *(retired §R2 — the connector never sees it)*. A configured fallback Item is explicitly **rejected** by rider §R3 (no substitute item).
- ~~**More than one active mapping for a product**: … the connector … MUST treat the state as unresolved (fail closed), not pick one.~~ **[RETIRED §R2 — DP2-side; the OQ-2 1:1 invariant + the multi-mapping check are DP2's at resolution time, pre-offer.]**
- ~~**Mapping confirmed after a prior `unmapped_item` ack**: … the connector MUST resolve and post idempotently …~~ **[RETIRED §R2 — re-offer/resolution is DP2-side. The connector's idempotency (Principle IV: same `sourceSystem`+`externalId` → same ERP doc) is retained and lives in spec 006.]**
- ~~**Stale/version-skewed mapping**: … it reads the *currently confirmed* mapping at resolution time …~~ **[RETIRED §R2 — the connector reads no mapping; DP2 resolves as-of-projection. No connector-side caching exists to go stale.]**
- ~~**ERPNext Item missing despite a confirmed mapping**: … an unresolved outcome (fail closed) …~~ **[RETIRED §R2 — the missing-Item/disabled-Item case fails-to-DLQ DP2-side per rider §R3. The connector never creates catalog masters (no import worker; OQ-8) — that prohibition is retained via FR-005.]**

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]`:
  ~~The connector MUST resolve each posting work-item sale line's `tenantProductRef`
  (DP2 tenant-product UUID, per `posting-feed.yaml`) to an ERPNext Item using the **confirmed**
  DP2-product → ERPNext-Item mapping defined in DP2 spec 013
  (`catalog/erpnext-item-map.yaml`, migration 0017).~~ **Resolution is now DP2-side at projection
  time** (rider §R2); the connector consumes the pre-resolved `erpnextItemRef` on the offered
  work-item (gated on `P-DP-012-EXT`) and addresses it generically per FR-002.
- **FR-002**: The connector MUST address the resolved ERPNext Item **generically** as
  `{doctype: "Item", name: <erpnext_item_ref>}` and MUST NOT fork ERPNext or copy a field-level
  ERPNext Item model (Principle II).
- **FR-003** `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]`:
  ~~The connector MUST treat **only** mappings in `state = confirmed` (and
  `retired_at = null`) as resolvable. `suggested` and `retired` mappings MUST NOT resolve a line
  (the confirmed-only invariant, DP2 data-model §3).~~ **The confirmed-only invariant is now
  enforced DP2-side** at projection time (rider §R2): unconfirmed/retired lines fail-to-DLQ in DP2
  before offer and never reach the connector. The connector no longer reads mapping state.
- **FR-004**: The connector MUST NOT call or re-implement DP2's suggest/confirm/retire review
  surface — those operations are `cookieAuth` (human Tenant-Admin via Retail-Tower-Console),
  explicitly not the `connectorBearer` machine scheme. The connector consumes only the *effect* of
  a confirmed mapping at posting time (Principle I).
- **FR-005** *(retained — reinforced by rider §R2)*: The connector MUST NOT invent an auto-match
  source for mappings. DP2 records
  `AUTO_MATCH_NO_SOURCE` (no ERPNext item-search op in the connector contract) and forbids an
  import worker (OQ-8); the connector MUST NOT create ERPNext Items, search ERPNext for matches,
  or otherwise act as a catalog import path. *(2026-06-05: rider §R2 strengthens this — with
  resolution moved fully DP2-side, the connector is item-resolution-free end to end: no lookup, no
  reach-back into DP2, no second copy of mapping truth.)*
- **FR-006** *(item-identity branch)* `[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]`:
  ~~When a sale line cannot be resolved to a confirmed Item (no active mapping,
  suggested-only, retired, ad-hoc with no reference, or confirmed-but-Item-absent), the connector
  MUST report `outcome = permanently_rejected` with `reason.category = unmapped_item` and fail
  closed — it MUST NOT guess an Item, post a partial invoice, or silently drop the line
  (Principle VI). It MUST NOT invent a connector-side retry; DP2 owns the dead-letter +
  reconciliation flag (DP2 spec 017) that follows a `permanently_rejected` outcome.~~ **Item-identity
  unresolved cases now fail-to-DLQ in DP2 before offer** (rider §R2) and never reach the connector,
  so the connector no longer emits the `unmapped_item` outcome. The fail-closed *reporting*
  discipline survives for the **UOM/`validation`** case via the **retained** FR-007 + FR-008.
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
- **FR-012**: An ad-hoc sale line (`tenantProductRef == null`) MUST **fail closed** — reported
  `permanently_rejected` / `unmapped_item`, identical to any unresolved product. The connector MUST
  NOT post an ad-hoc line against a catch-all/"miscellaneous" Item. *(Signed 2026-06-04, Option A —
  see Clarifications.)* A configured fallback Item is a possible future signed opt-in, not the
  default; if ever introduced it MUST be an explicit, configured, signed decision (never an
  implicit guess).
- **FR-013**: Every DP2 reference in this spec and its decision records MUST cite a real path in
  the Data-Pulse-2 repository (verified to locate and confirm the claim); the connector MUST NOT
  re-derive DP2's model (Principle I, `dp2-citation-verification`).

### Key Entities *(include if feature involves data)*

> **[RECONCILED 2026-06-05 — Q-CON-004 / rider 011-DR-POSTING-R1 §R2]** Item *resolution* moved DP2-side; the entries below describe what the connector now **applies**, not what it resolves. Strike-through marks the superseded connector-side-resolution wording (preserved for history).
- **Sale-line product reference (`tenantProductRef`)**: a nullable DP2 tenant-product UUID on each
  posting work-item sale line (`posting-feed.yaml`). Null = ad-hoc line. Lineage only — ~~the connector's input to
  resolution~~ *(retired §R2: the connector no longer resolves it; DP2 resolves item identity at work-item projection)*; it is *not* owned by the connector.
- **ERPNext Item mapping (`erpnext_item_map`)**: the DP2-side identity mapping (DP2 spec 013,
  migration 0017): `tenant_product_id` → `erpnext_item_ref` (opaque ERPNext Item code/name), with
  lifecycle `state ∈ {suggested, confirmed}`, append-only retire (`retired_at`), and an
  optimistic-concurrency `version`. ~~The connector reads only the **confirmed, non-retired** row.~~
  **[RETIRED 2026-06-05 — superseded by DP2 rider 011-DR-POSTING-R1 §R2; ratified Q-CON-004. Preserved for history.]** Per §R2 the connector **MUST NOT read this map, reach back into DP2, or hold a copy** — DP2 resolves the `confirmed, non-retired` row at projection and stamps the result onto the work-item; the connector only applies it.
- **ERPNext Item reference (`erpnextItemRef`)**: the **pre-resolved** identity the connector applies — a generic `{doctype: "Item", name}` address
  (Principle II), supplied DP2-side on the work-item (DP-012 `posting-feed.yaml` `SaleLine.erpnextItemRef`, v1.1.0-draft). Carries no copied ERPNext field model. ~~the resolution output~~ *(retired §R2: the connector does not produce it; it receives it)*.
- **Unresolved outcome**: ~~a `permanently_rejected` `connectorAckOutcome` … for an unresolved product~~ **[RETIRED 2026-06-05 — §R2: a line that cannot resolve fails-to-DLQ in DP2 *before* the work-item is offered, so the connector never sees an item-unresolved line. Preserved for history.]** The connector still emits `validation` (`permanently_rejected`) for an **unmapped UOM** (FR-008/US4 — retained). Visible to DP2 for dead-letter + reconciliation (017); never a silent default. The decision to re-offer the work-item is DP2's, not the connector's.

## Success Criteria *(mandatory)*

### Measurable Outcomes

> **[RECONCILED 2026-06-05 — §R2]** SC-001/SC-003 originally measured connector-side *item* resolution; that path is retired (DP2-side now). Re-scoped below to the surviving connector role (apply the pre-resolved ref; UOM reconciliation). Strike-through preserves the original.
- **SC-001**: ~~A reviewer can trace every sale-line product reference … to a documented resolution path that ends in either a single confirmed ERPNext Item or a typed unresolved outcome~~ **[RETIRED §R2 — item resolution is DP2-side; superseded.]** *(Re-scoped:* every offered work-item line carries a pre-resolved `erpnextItemRef` the connector applies verbatim — **zero** connector-side guesses, lookups, or dropped lines; a line that could not resolve never reaches the connector, having failed-to-DLQ in DP2 before offer.*)*
- **SC-002**: 100% of DP2 references in the spec and its decision records resolve to a real
  Data-Pulse-2 repository path and confirm the claim made (no phantom citations).
- **SC-003**: ~~Every unresolved case is reported … `unmapped_item` for product cases, `validation` for an unmapped UOM~~ **[Re-scoped §R2:** the connector no longer emits `unmapped_item` (item-unresolved is a DP2-side pre-offer DLQ case); it still emits `validation` (`permanently_rejected`) for an **unmapped UOM** — drawn from DP2's existing closed set, **no new wire reason code invented**.*]*
- **SC-004**: A reviewer confirms the connector neither calls DP2's tenant-admin review surface
  (`cookieAuth`) nor creates/searches ERPNext Items — i.e. no catalog-import or item-search path
  appears anywhere in the spec (Principle I/II, `AUTO_MATCH_NO_SOURCE`, OQ-8).
- **SC-005**: The ad-hoc line policy is explicit and **signed** (2026-06-04: fail-closed —
  `permanently_rejected` / `unmapped_item`, no catch-all Item) before spec 006 (sales posting)
  implements line resolution. ✅ Signed (see Clarifications / FR-012).
- **SC-006** *(deferred — bench)*: ~~On a staging ERPNext v15 site, a posting work-item with a
  confirmed mapping resolves to its Item, and a work-item with no confirmed mapping acks
  `permanently_rejected` / `unmapped_item`~~ **[Re-scoped §R2:** on a staging ERPNext v15 site, a posting work-item with a pre-resolved `erpnextItemRef` posts to that Item; the item-unmapped case is exercised DP2-side (pre-offer DLQ), not here. The connector's bench case is the UOM `validation` rejection.*]* Idempotent on a DP2 re-offer. Marked
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
- **Confirmed mappings must actually exist in DP2 at posting time.** **DP2-side** resolution depends on a
  Tenant Admin having confirmed each product's mapping in Retail-Tower-Console. Until a product is
  confirmed, ~~its lines are unresolved (FR-006)~~ *(FR-006 item-branch retired §R2)* **its lines fail-to-DLQ in DP2 before the work-item is offered** — a DP2-side data-readiness dependency,
  tracked outside this spec's slice graph (analogous to the spec-003 token-scope dependency).
- **Signed UOM decision** (`docs/decisions/mapping-uom.md`, Option A) — input to FR-008.
- **Spec 003 policy** (auth, idempotency, error taxonomy, correlation, secrets) — substrate for
  FR-007/FR-010/FR-011.
- **Ad-hoc line policy** (FR-012) — ✅ signed 2026-06-04 (fail closed; no catch-all Item). No
  longer an open decision blocking spec 006.
