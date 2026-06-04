# Phase 0 Research — Product–ERPNext Item Mapping (Posting Resolution)

All findings are grounded in the **read-only** Data-Pulse-2 repository
(`C:\Users\user\Documents\GitHub\Data-Pulse-2`). Every cited path was verified to locate and
confirm the claim (FR-013, Principle I, `dp2-citation-verification`).

## Decision 1 — Resolution direction: DP2-product → ERPNext-Item, NOT catalog export

**Decision**: Spec 004 defines the connector's mapping-resolution responsibility — resolving a
sale line's `tenantProductRef` to a confirmed ERPNext Item — and explicitly does **not** export
product/price/UOM/barcode data from ERPNext to DP2 (the README's original framing).

**Rationale** (the README roadmap drifted from DP2's authoritative contracts; same class of drift
as spec 003's auth-direction flip):

- The only `connectorBearer` machine surface, `erpnext-connector/posting-feed.yaml`, has exactly
  two operations — `connectorPullPostings` and `connectorAckOutcome` (lines 106, 149). There is
  **no** product/price/item-export or catalog-push operation.
- DP2 documents the absence: `catalog/erpnext-item-map.yaml` records `AUTO_MATCH_NO_SOURCE` —
  *"no ERPNext item-search op exists in the 012 connector contract"* — and OQ-8 *"forbids an import
  worker"* (lines 22–28).
- DP2 is the **catalog authority**: `catalog/read-down.yaml` (spec 010) and
  `catalog/erpnext-item-map.yaml` (spec 013) both state the 003 Tenant Catalog stays authoritative
  for the retail product; **ERPNext owns accounting-Item identity only** (item-map lines 13–17).
  The POS catalog flows DP2 → POS (read-down) from DP2's own `tenant_products`, not from ERPNext.
- The reverse direction (DP2 pulling a connector-exposed product API) is barred by the ratified
  Gate-G4 clarification — constitution v1.0.1: *"the connector is the client; DP2 makes no outbound
  calls."*

**Alternatives considered**:
- *Export from ERPNext (README framing)* — rejected: no DP2 ingest contract exists; inventing the
  wire shape violates Principles I and VII.
- *DP2 pulls a connector product API* — rejected: violates Gate G4 (connector is the client).
- *Record 004 blocked on a DP2 ingest contract* — rejected by the user (signed Option A): the
  identity-mapping responsibility is real, contract-backed, and de-risks spec 006 now.

## Decision 2 — Resolution input: the confirmed `erpnext_item_map`

**Decision**: Resolve `tenantProductRef` → ERPNext Item via the DP2 `erpnext_item_map`
(`catalog/erpnext-item-map.yaml`, DP2 spec 013, migration 0017), consuming **only** rows in
`state = confirmed` with `retired_at = null`.

**Rationale**:
- `posting-feed.yaml` lines 481–484: the sale line carries `tenantProductRef` (nullable DP2
  tenant-product UUID) and states *"The connector maps it to an ERPNext Item (013) behind this
  contract."*
- The mapping carries `tenant_product_id`, `erpnext_item_ref` (opaque ERPNext Item code/name,
  *"no FK, version-independent (012 O-6)"*, item-map lines 315–321), `state ∈ {suggested,
  confirmed}`, append-only `retired_at`, and an optimistic-concurrency `version`.
- **Confirmed-only invariant** (item-map lines 32–33, 367–368, data-model §3): *"Only confirmed
  mappings are resolvable at posting time."* A `suggested` or `retired` row must not resolve.
- **1:1 invariant** (OQ-2, item-map lines 120–123): at most one active mapping per
  `tenant_product_id`; a second active suggestion is `409 conflict`. The connector relies on this;
  observing two confirmed mappings is fail-closed, not pick-one.

**Alternatives considered**:
- *Resolve against any (incl. suggested) mapping* — rejected: violates the confirmed-only invariant
  and would post against an unreviewed identity.
- *Connector creates / searches ERPNext Items* — rejected: `AUTO_MATCH_NO_SOURCE` + OQ-8 forbid an
  import/search path; the connector creates no catalog masters.

## Decision 3 — Mapping lifecycle ownership: DP2 (human Tenant-Admin), not the connector

**Decision**: The connector neither builds nor calls the suggest/confirm/retire review surface; it
consumes only the *effect* of a confirmed mapping at posting time.

**Rationale**: The `erpnext-item-map.yaml` operations
(`tenantAdminListErpnextItemMappings`/`Suggest`/`Confirm`/`Retire`) are all `cookieAuth` — the
httpOnly `dp2_session` human Tenant-Admin scheme (lines 39–50, 274–284), explicitly *"NOT the 012
`connectorBearer` machine scheme."* The review is a human action in Retail-Tower-Console, which
talks only to DP2 (011 boundaries). This keeps Principle I intact.

## Decision 4 — Unresolved outcome: `permanently_rejected` with a closed `reason.category`

**Decision**: Every unresolved case fails closed as `connectorAckOutcome` `outcome =
permanently_rejected`, with `reason.category` drawn from DP2's **closed** set — `unmapped_item` for
product cases, `validation` for an unmapped UOM. No new wire reason is invented; the connector does
not self-retry.

**Rationale**:
- `posting-feed.yaml` `OutcomeAckRequest` (lines 521–563): outcome enum is `posted |
  failed_transient | permanently_rejected`. `permanently_rejected` is *"non-retryable (carries
  `reason`); DP2 dead-letters it and raises a reconciliation flag (017)"*; `failed_transient` is the
  *retryable* path that *"DP2 re-offers... bounded by a retry budget"* and carries no reason.
- `RejectionReason.category` (line 609) is a closed set:
  `validation | closed_period | unmapped_item | unmapped_account | other`. DP2 already reserved
  **`unmapped_item`** for exactly this connector inability-to-resolve case.
- An unmapped product, suggested-only, retired, or confirmed-but-Item-absent line → `unmapped_item`.
- An unmapped UOM → `validation` (there is **no** `unmapped_uom` category; a UOM problem is a
  line-validation failure — routing it as `unmapped_item` would misdirect the 017 reconciliation).
- Re-offer is DP2's decision (it owns DLQ + 017 reconciliation). The connector does not invent a
  `failed_transient` loop for unmapped products. (The contract shows `dlqueued` + the 017 flag; it
  does **not** describe a re-drive mechanism — so the policy says "when DP2 re-offers" and stops,
  asserting no mechanism the connector cannot see.)

## Decision 5 — UOM and money reconciliation reuse signed/contract shapes

**Decision**: Reconcile the DP2 free-text `unit` per the signed UOM decision; carry money as
exact-decimal + ISO-4217.

**Rationale**:
- Signed UOM decision `docs/decisions/mapping-uom.md` (Option A): connector-side unit→ERPNext-UOM
  map; an unmapped unit fails closed. No new unit decision opened here.
- `posting-feed.yaml` `DecimalAmount` (line 293) + `CurrencyCode` (line 300): money is an
  exact-decimal string paired with an ISO-4217 code — *never* a float.

## Decision 6 — Ad-hoc line policy: fail closed (signed intra-spec)

**Decision**: An ad-hoc line (`tenantProductRef == null`) fails closed as `permanently_rejected` /
`unmapped_item` — no configured catch-all Item.

**Rationale**: Signed by the user 2026-06-04 (Option A; spec Clarifications). Principle VI: a
catch-all Item would distort ERPNext item-level reporting and could mask a real catalog gap. A
fallback Item remains a possible *future* explicit signed opt-in, not the default. This is the only
intra-spec decision and is recorded inside the resolution policy doc (not a standalone record).

## Open dependencies (not blockers to this policy)

- **Confirmed mappings must exist in DP2 at posting time** — a DP2-side data-readiness dependency
  (a Tenant Admin must confirm each product's mapping in Retail-Tower-Console). Until then, lines
  are unresolved (FR-006). Tracked outside this spec's slice graph, analogous to the spec-003
  token-scope dependency.
- **Bench resolution (SC-006)** — deferred to a staging ERPNext v15 site (standing-rules §6).
