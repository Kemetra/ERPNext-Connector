# Phase 0 Research: DocType Mapping Reference

**Feature**: 002-doctype-mapping-reference | **Date**: 2026-06-04

Source: survey of the Data-Pulse-2 backend (`C:\Users\user\Documents\GitHub\Data-Pulse-2`).
DP2 is a TypeScript/NestJS + PostgreSQL 16 monorepo; the domain model lives in
`packages/db/src/schema/` (Drizzle) with SQL migrations in `packages/db/drizzle/`, and the
integration contracts in `packages/contracts/openapi/`. There are **no open
NEEDS CLARIFICATION items** — the Technical Context is fixed (Markdown artifact citing DP2).

---

## Decision 1: Authoritative DP2 sources for the matrix (cite, don't redefine)

**Decision**: Each matrix row's Retail Tower counterpart cites a specific DP2 artifact.
**Code/contracts outrank prose** (spec Assumption). The authoritative sources are:

| ERPNext concept | DP2 counterpart | Authoritative DP2 source (cite) |
|-----------------|-----------------|---------------------------------|
| Company | `tenants` table | `packages/db/src/schema/tenants.ts` |
| Warehouse | `stores` table | `packages/db/src/schema/stores.ts` |
| Item | `tenant_products` (+ `global_products`, `store_product_overrides`) | `packages/db/src/schema/catalog/tenant-products.ts` |
| Item Barcode | `product_aliases` (`identifier_type='barcode'`) | `packages/db/src/schema/catalog/product-aliases.ts` |
| UOM | free-text `unit` / `stocking_unit` (no master) | `schema/sales/sale-lines.ts`, `schema/inventory/stock-movements.ts` |
| Price List | `price_history` + `default_price` (no PriceList entity) | `packages/db/src/schema/catalog/price-history.ts` |
| POS/Sales Invoice | `sales` + `sale_lines` | `packages/db/src/schema/sales/sales.ts`, `sale-lines.ts` |
| Payment Entry | not modeled (voucher stub only) | `packages/contracts/openapi/pos-payments/vouchers.yaml` |
| Return/Refund | `sale_refunds` + `sale_voids` | `packages/db/src/schema/sales/sale-terminal-events.ts` |
| Product→Item link | `erpnext_item_map` (migration 0017) | `schema/catalog/erpnext-item-map.ts`, `drizzle/0017_erpnext_item_map.sql` |
| ERPNext doc addressing | `ErpnextDocumentRef = {doctype, name}` | `packages/contracts/openapi/erpnext-connector/posting-feed.yaml` |

**Rationale**: DP2 already drafted this mapping (specs 011/013 + the shipped `erpnext_item_map`
table + the `posting-feed.yaml` connector contract). Citing it honors Principle I and avoids
a second source of truth. The stale `docs/ROADMAP-ERP.md` in DP2 is noted as superseded
(FR-007) — proof that prose drifts and code/contracts must win.

**Alternatives considered**: Re-deriving the mapping in the connector repo — rejected
(Principle I; guaranteed drift). Citing DP2 prose docs (specs 011/013) as primary — rejected;
they are cited as *secondary* context, with schema/contract as primary.

---

## Decision 2: The three known status calls (carried from spec, recorded here)

These are recorded statuses, not user questions (resolved in clarify):

- **UOM → Decision needed.** DP2 has no UOM master; unit is free-text (`sale_lines.unit`,
  `stocking_unit`). DP2's own open question (013 OQ-3). A decision record
  (`docs/decisions/mapping-uom.md`) states the question (how connector reconciles free-text
  units with ERPNext UOM) and gates spec 004/006 work touching units.
- **Price List → Resolved (reference only).** DP2 amounts (`price_history` / `default_price`)
  are authoritative; ERPNext Price List is a document-validity reference only (DP2 013 §4).
  No decision record needed; recorded as Resolved with the reference-only note.
- **Payment Entry → Deferred** to spec 006 (sales posting / tender). DP2 models no tender;
  `posTotal` is the sale total, not tender. Recorded with owning spec.
- **Customer → Deferred / ERPNext-owned.** DP2 has no Customer entity (walk-in retail);
  recorded as ERPNext-owned with a decision record placeholder if a connector default is
  needed for posting.

---

## Decision 3: ERPNext addressing stays generic (`{doctype, name}`)

**Decision**: The matrix's "ERPNext side" addresses documents only via the generic
`ErpnextDocumentRef = {doctype, name}` that DP2's connector contract exposes — never ERPNext
field-level names.

**Rationale**: DP2's connector contract (012 O-6) deliberately keeps the connector speaking
Retail-Tower terms, with `{doctype, name}` the only ERPNext-specific addressing on the wire,
for version-independence. The reference must mirror this (FR-004, Principle II) so a future
ERPNext version change doesn't invalidate the mapping at the field level.

**Alternatives considered**: Mapping to specific ERPNext DocType fields now — rejected;
couples the reference to an ERPNext version and pre-empts the field-level work owned by
spec 006.

---

## Open items

None. All Technical Context is resolved; no `NEEDS CLARIFICATION` remains.
