# Quickstart — Verifying the Product–ERPNext Item Mapping Resolution Policy

How a reviewer (or operator, at staging time) verifies spec 004. This is a **policy** spec — most
checks are review-time; bench checks are deferred (standing-rules §6).

## Review-time verification (now — no bench)

1. **Resolution path is complete and binary.** Open `docs/decisions/product-item-mapping-resolution.md`
   (produced by `/speckit-implement`). Confirm every sale-line condition lands in exactly one of two
   terminal states — a single confirmed ERPNext Item, or a typed `permanently_rejected` outcome —
   with **no** third "absorbed / defaulted / dropped" path (data-model decision table; SC-001).

2. **Confirmed-only invariant.** Confirm the policy resolves only `state = confirmed`,
   `retired_at = null` mappings; `suggested` and `retired` route to `unmapped_item` (FR-003, SC-004).

3. **No catalog import / export / search.** Confirm the policy nowhere exports ERPNext catalog to
   DP2, calls DP2's `cookieAuth` review surface, or searches/creates ERPNext Items
   (`AUTO_MATCH_NO_SOURCE`, OQ-8; FR-004/005, SC-004).

4. **Reason-category mapping is correct.** Confirm unmapped **product** → `unmapped_item`, unmapped
   **UOM** → `validation` (not `unmapped_item`); no new wire reason invented (FR-006/007/008, SC-003).

5. **Ad-hoc line fails closed.** Confirm a null `tenantProductRef` → `permanently_rejected` /
   `unmapped_item`, with no catch-all Item (FR-012, SC-005 — signed).

6. **Every DP2 citation locates.** For each DP2 path cited in the policy + research, confirm it
   resolves in `C:\Users\user\Documents\GitHub\Data-Pulse-2` and confirms the claim (FR-013, SC-002).

7. **No secrets, generic addressing.** Confirm the policy forbids secrets/tokens in logs/errors/UI,
   addresses ERPNext only as `{doctype, name}`, and traces via DP2 `request_id` (FR-002/011).

## Bench verification (deferred — staging ERPNext v15)

> ⏳ BENCH-VALIDATION — not run locally, not claimed until executed on a real bench AND DP2 holds
> confirmed mappings (standing-rules §6). Covers SC-006.

- A posting work-item whose sale line has a **confirmed** mapping resolves to its ERPNext Item.
- A work-item with **no** confirmed mapping acks `permanently_rejected` / `unmapped_item` and posts
  nothing.
- On a DP2 re-offer after the mapping is confirmed, the same work-item resolves and posts
  idempotently (same `sourceSystem`+`externalId` → same document, no duplicate).

## Done when

- The resolution policy is reviewed and signed (G1 reference sign-off).
- All review-time checks (1–7) pass; bench checks (SC-006) marked deferred.
- The ad-hoc-line decision is signed (done — Clarifications) so spec 006 inherits no open mapping.
