# Phase 1 Data Model — Product–ERPNext Item Mapping (Posting Resolution)

This is a **conceptual** model for the resolution policy — not a connector DB schema (no DocType,
no migration; spec 006 implements). Every entity is owned by DP2 or is a resolution concept; the
connector reads inputs and emits one outcome.

## Entities

### 1. Sale-line product reference (`tenantProductRef`) — INPUT (DP2-owned)

| Field | Type | Notes |
|-------|------|-------|
| `tenantProductRef` | UUID \| null | DP2 tenant-product id on a posting work-item sale line (`posting-feed.yaml`). **Null = ad-hoc line.** The connector's resolution input; not connector-owned. |

Source: `posting-feed.yaml` `SaleLine.tenantProductRef` (lines 481–488).

### 2. ERPNext Item mapping (`erpnext_item_map`) — INPUT (DP2-owned, spec 013)

| Field | Type | Notes |
|-------|------|-------|
| `tenant_product_id` | UUID | The DP2 product the mapping is for (1:1 active — OQ-2). |
| `erpnext_item_ref` | string (1..140) | Opaque ERPNext Item code/name; no FK, version-independent (012 O-6). |
| `state` | enum `{suggested, confirmed}` | **Only `confirmed` resolves** (confirmed-only invariant). |
| `retired_at` | timestamp \| null | Append-only soft-delete; non-null = not resolvable. |
| `version` | int ≥ 1 | Optimistic-concurrency token (connector does not own/mutate it). |

Source: `catalog/erpnext-item-map.yaml` `ErpnextItemMapping` (lines 340–400), migration 0017.
**Connector reads only `state = confirmed` AND `retired_at = null`.**

**Lifecycle (DP2 Tenant-Admin owned, `cookieAuth` — connector does not call):**

```
(none) --suggest--> suggested --confirm--> confirmed --retire--> retired
                                                ^                    |
                                                |   re-point = retire + fresh suggest
                                                +--------------------+
```

### 3. ERPNext Item reference — RESOLUTION OUTPUT (success)

| Field | Type | Notes |
|-------|------|-------|
| `doctype` | const `"Item"` | Generic addressing only (Principle II). |
| `name` | string | = the mapping's `erpnext_item_ref`. No copied ERPNext field model. |

Source: generic `{doctype, name}` form (`posting-feed.yaml` `ErpnextDocumentRef`, O-6, lines 565–583).

### 4. Unresolved outcome — RESOLUTION OUTPUT (failure, fail-closed)

| Field | Type | Notes |
|-------|------|-------|
| `outcome` | const `"permanently_rejected"` | Uniform across all unresolved cases. |
| `reason.category` | enum (DP2 closed set) | `unmapped_item` (product) or `validation` (UOM). No new code. |
| `reason.message` | string (1..1000) | Human detail; **no secrets / no sensitive ERPNext internals**. |

Source: `posting-feed.yaml` `OutcomeAckRequest` + `RejectionReason` (lines 521–614).

## Resolution decision table (the policy core)

| Input condition | Outcome | `reason.category` |
|-----------------|---------|-------------------|
| `tenantProductRef` has a **confirmed**, non-retired mapping; Item exists; UOM maps | `posted` (resolved Item) | — |
| `tenantProductRef` **null** (ad-hoc line) | `permanently_rejected` | `unmapped_item` |
| No active mapping for `tenantProductRef` | `permanently_rejected` | `unmapped_item` |
| Mapping exists but `state = suggested` | `permanently_rejected` | `unmapped_item` |
| Mapping `retired` | `permanently_rejected` | `unmapped_item` |
| Two confirmed mappings observed (invariant breach) | `permanently_rejected` (fail closed, never pick) | `unmapped_item` |
| Confirmed `erpnext_item_ref` but Item absent in ERPNext | `permanently_rejected` (never create) | `unmapped_item` |
| Resolved Item but DP2 `unit` has no UOM mapping | `permanently_rejected` | `validation` |

**Invariant**: exactly two terminal states per line — `posted` (a single confirmed Item) or
`permanently_rejected` (typed). No third "absorbed / defaulted / dropped" path (Principle VI).

## Idempotency / replay (documented; implemented in spec 006)

- Replay key = `sourceSystem` + `externalId` (`posting-feed.yaml` O-3) → the same ERPNext document.
- When DP2 re-offers a previously `unmapped_item` work-item after the mapping is confirmed, the
  connector resolves and posts without duplicating the ERP document. The **re-offer decision is
  DP2's** (it owns DLQ + 017 reconciliation); the connector does not self-retry.

## Money representation

- Every monetary value: exact-decimal string + ISO-4217 `currency_code` (`DecimalAmount` /
  `CurrencyCode`). Never a float.
