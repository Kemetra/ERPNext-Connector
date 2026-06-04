# Phase 1 Data Model: DocType Mapping Reference

**Feature**: 002-doctype-mapping-reference | **Date**: 2026-06-04

This feature produces **documentation entities**, not stored data. No DocType, no schema,
no migration (constitution Principle VII). The "entities" below define the structure of the
mapping reference and its decision records.

---

## Entity: Mapping Matrix Row

One row per ERPNext concept in `docs/architecture/doctype-mapping-reference.md`.

| Column | Meaning | Source / rule |
|--------|---------|---------------|
| ERPNext concept | The ERPNext-side concept name | e.g. Item, Warehouse, POS Invoice |
| Retail Tower counterpart | The DP2 entity/contract that models it | cited from DP2 (FR-003) |
| Owner of truth | Which system is authoritative | DP2 / ERPNext (e.g. accounting/GL = ERPNext) |
| Status | `Resolved` / `Decision needed` / `Deferred to NNN` | FR-002 |
| DP2 source citation | Locatable path in the DP2 repo | schema/contract preferred over prose (Assumption) |

**Validation rules**:
- Every listed concept (Company, Warehouse, Item, Barcode, UOM, Price List, Sale/Invoice,
  Payment, Return) MUST appear as a row (FR-001, SC-001).
- Every row MUST have all five columns populated; the citation MUST be locatable (SC-004).
- ERPNext-side addressing, where shown, MUST be generic `{doctype, name}` (FR-004).

## Entity: Mapping Decision Record

One Markdown file per "Decision needed" row, under `docs/decisions/`.

| Field | Meaning |
|-------|---------|
| Concept | The ambiguous mapping (e.g. UOM) |
| Question | The specific open question (e.g. how to reconcile free-text units with ERPNext UOM) |
| Options | The candidate resolutions with trade-offs |
| Recommendation | Optional suggested resolution |
| Sign-off | An explicit line: signed (by/date) or open |
| Blocks | The later spec(s) gated until signed (FR-005, SC-005) |

**State transitions**: `open` → `signed`. An `open` record blocks the named downstream
spec; a `signed` record unblocks it. (No finer state machine — docs artifact.)

## Entity: Product-to-Item Correlation (concept-level)

A concept-level description (in the matrix + reference prose) of how a confirmed Retail
Tower product links to an ERPNext Item, citing DP2's `erpnext_item_map`:

- DP2 holds `erpnext_item_map` (migration 0017): `tenant_product_id` → `tenant_products`,
  `erpnext_item_ref` (text, no FK — ERPNext is external), `state ∈ {suggested, confirmed}`,
  1:1 active invariant per `(tenant, tenant_product)`.
- Only `confirmed` rows are resolvable for posting. The connector consumes this; it does not
  own the correlation (Principle I).
- Recorded at concept level only (FR-009, FR-010) — field-level posting is spec 006.

---

## Explicitly absent (by design — Principle VII / FR-008)

- No connector DocType, schema, migration, or mapping code.
- No `contracts/` — the connector↔DP2 contract is owned by DP2 (`posting-feed.yaml`), cited.
- No field-level ERPNext document construction (owned by spec 006).
