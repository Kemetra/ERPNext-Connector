# Implementation Plan: Product–ERPNext Item Mapping (Posting Resolution)

**Branch**: `004-004-product-erpnext` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-product-erpnext-item-mapping/spec.md`

## Summary

Produce a reviewed **product–ERPNext-Item mapping resolution policy**: how the connector resolves
each posting work-item sale line's `tenantProductRef` (a DP2 tenant-product UUID) to a concrete
ERPNext **Item** using the *confirmed* DP2-side `erpnext_item_map` (DP2 spec 013), addressing
ERPNext generically as `{doctype, name}`. The policy **cites** DP2's authoritative contracts —
it does not re-derive them or export catalog data from ERPNext (no such DP2 contract exists; the
reverse direction is barred by Gate G4). Its spine is the **unhappy path**: any line that cannot
resolve to a confirmed Item fails closed as `permanently_rejected` with a structured
`reason.category` from DP2's closed set (`unmapped_item` for product cases, `validation` for an
unmapped UOM) — never a silent guess, drop, or catch-all (Principle VI). Documentation + policy
artifact only: no connector code (resolution/UOM-map/posting land in spec 006, per Principle VII).

## Technical Context

**Language/Version**: N/A — Markdown policy artifact. (Future resolution code is Python/Frappe v15
per spec 001; produced in spec 006, not here.)

**Primary Dependencies**: Data-Pulse-2 backend (`C:\Users\user\Documents\GitHub\Data-Pulse-2`) as
the authoritative read-only reference:
- `packages/contracts/openapi/catalog/erpnext-item-map.yaml` (DP2 spec 013, migration 0017) — the
  `tenant_product_id → erpnext_item_ref` mapping, lifecycle (`suggested`/`confirmed`/retired),
  confirmed-only invariant, `AUTO_MATCH_NO_SOURCE`, OQ-2/OQ-7/OQ-8.
- `packages/contracts/openapi/erpnext-connector/posting-feed.yaml` — `tenantProductRef` on the
  sale line; the `connectorAckOutcome` outcome enum (`posted | failed_transient |
  permanently_rejected`) and `RejectionReason.category` closed set; `DecimalAmount`/`CurrencyCode`;
  generic `{doctype, name}` addressing (O-6).
- `packages/contracts/openapi/catalog/read-down.yaml` (DP2 spec 010) — establishes DP2 as the
  catalog authority (cited to bound scope, not consumed).

**Storage**: N/A for this feature. (The connector-side unit→UOM map and any mapping cache are a
spec-006 implementation concern; the policy states the *requirement*, not the mechanism.)

**Testing**: Reviewer verification against acceptance scenarios + DP2 citation-locates. No
automated tests for a policy artifact. Bench resolution (SC-006) is a deferred staging validation
(no local bench; standing-rules §6) and additionally depends on DP2 holding *confirmed* mappings.

**Target Platform**: N/A (policy document under `docs/`).

**Project Type**: Documentation / policy (single project).

**Performance Goals**: N/A.

**Constraints**: Cite DP2, never re-derive (FR-013, Principle I); no catalog export from ERPNext
and no reverse pull (Gate G4, constitution v1.0.1); generic `{doctype, name}` addressing (FR-002,
Principle II); confirmed-only resolution (FR-003); no auto-match / no Item creation
(`AUTO_MATCH_NO_SOURCE`, OQ-8, FR-005); fail-closed unresolved surfacing (FR-006..008/012,
Principle VI); reuse the spec-003 ack/idempotency/correlation/secrets substrate (FR-007/010/011);
docs-only (Principle VII).

**Scale/Scope**: One resolution-policy document under `docs/decisions/`. The single intra-spec
decision (ad-hoc line policy) is already signed inside the spec's Clarifications and folds into the
policy doc — no separate decision record. No data volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial evaluation (pre-design):**

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Data-Pulse-2 is the only orchestration boundary | ✅ Pass | The connector consumes the *confirmed* DP2 mapping at posting time; it never calls DP2's tenant-admin review surface (`cookieAuth`) and never exports catalog from ERPNext (FR-004). The policy cites DP2's contracts as authoritative (FR-013). |
| II. No ERPNext fork (connector stays thin) | ✅ Pass | The resolved Item is addressed generically as `{doctype: "Item", name}` (FR-002); no ERPNext field model is copied or forked. |
| III. Additive & upgrade-safe changes | ✅ Pass (N/A) | Documentation only; no schema/migration/version pin. |
| IV. Idempotent mutations | ✅ Pass (documented, not implemented) | The policy *states* the replay-safety requirement (FR-010: same `sourceSystem`+`externalId` → same ERP doc on a DP2 re-offer) but implements no mutation. Per standing-rules §0, IV *applies* once mutation begins (spec 006); 004 records the requirement so 006 inherits it. |
| V. Observable failures | ✅ Pass | Unresolved/error outcomes are traceable via the spec-003 correlation policy (DP2 `request_id`) with no secret leak (FR-011, Gate G4). Reuses the spec-003 typed taxonomy rather than inventing one. |
| **VI. Fiscal & stock truth is never hidden** | ✅ Pass (**the principle this spec most exercises**) | The fail-closed unresolved surfacing IS the Principle VI enforcement: an unmapped/suggested-only/retired/Item-absent product, an ad-hoc line, and an unmapped UOM each become an explicit typed `permanently_rejected` outcome (FR-006/007/008/012) — never a silent guess, drop, or catch-all Item. DP2 sees every gap for 017 reconciliation. |
| VII. Spec-driven, contract-first delivery | ✅ Pass | This is the catalog-resolution contract policy itself; it is reviewed/signed before any resolution code (spec 006). The ad-hoc decision is signed (Clarifications) so no ambiguous mapping leaks into 006. |

**Result**: PASS — no violations. Complexity Tracking empty.

**Post-design re-evaluation (after Phase 1):** See [Post-Design Constitution Re-Check](#post-design-constitution-re-check).

## Project Structure

### Documentation (this feature)

```text
specs/004-product-erpnext-item-mapping/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — authoritative DP2 citations + the resolution-direction call
├── data-model.md        # Phase 1 — the resolution concepts (mapping, outcome, reason-category map)
├── quickstart.md        # Phase 1 — how a reviewer verifies the resolution policy
├── spec.md              # Feature specification
└── checklists/
    └── requirements.md  # Spec quality checklist (16/16 pass)
```

*No `contracts/` directory: the relevant interface contracts (`erpnext-item-map.yaml`,
`posting-feed.yaml`) already exist and are owned by DP2. This policy cites them. Emitting a
contract here would create a second source of truth (FR-013 / Principle I).*

### Source Code (repository root)

```text
docs/
├── decisions/
│   └── product-item-mapping-resolution.md  # the resolution policy (FR-001..FR-013), incl.
│                                           # the signed ad-hoc-line decision (intra-spec)
└── architecture/
    └── doctype-mapping-reference.md        # (existing, spec 002) — referenced; the resolution
                                            # policy extends its Item/UOM rows, does not duplicate
```

**Structure Decision**: The resolution policy lives at
`docs/decisions/product-item-mapping-resolution.md` (a decision/policy artifact per the README
layout, mirroring spec 003's `data-pulse-auth-and-api-policy.md`). The ad-hoc-line policy is an
*intra-spec* sub-decision already signed in the spec's Clarifications, so it folds into this one
policy doc rather than getting a standalone `docs/decisions/` record (those — UOM, Customer,
token-scope — are reserved for *cross-spec* decisions). The spec-002 mapping reference
(`docs/architecture/doctype-mapping-reference.md`) is referenced for the Item/UOM rows; the
resolution policy extends, not duplicates, it. No `contracts/`; no code.

## Complexity Tracking

> No Constitution Check violations. No complexity to justify. (Section intentionally empty.)

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (research.md + data-model.md + quickstart.md; contracts/ skipped with
reason):

- **Principle I (DP2 boundary)**: Confirmed — the policy cites DP2's mapping + posting contracts;
  the connector consumes the confirmed mapping's effect, never the review surface, never an export.
- **Principle II (no fork)**: Confirmed — resolved Item addressed only as `{doctype, name}`.
- **Principle IV (idempotent, documented)**: Confirmed — replay-safety is stated as a requirement
  for spec 006 to implement; 004 mutates nothing and over-claims nothing about DP2's re-offer
  mechanism (it cites DLQ + 017 reconciliation and stops).
- **Principle V (observable)**: Confirmed — correlation via DP2 `request_id`; no secret leak.
- **Principle VI (truth never hidden)**: Confirmed — every unresolved case is an explicit typed
  outcome mapped onto DP2's closed `reason.category` set; no silent path exists. This is the spec's
  load-bearing principle.
- **Principle VII (no implementation)**: Confirmed — policy + signed intra-spec decision only; no
  resolution/UOM-map/posting code; gates spec 006.

**Result**: PASS (post-design). No new violations. Ready for `/speckit-tasks`.
