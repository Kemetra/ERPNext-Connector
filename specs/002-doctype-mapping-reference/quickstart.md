# Quickstart: Using & Verifying the DocType Mapping Reference

**Feature**: 002-doctype-mapping-reference | **Date**: 2026-06-04

How a reviewer or planner uses the mapping reference once it exists at
`docs/architecture/doctype-mapping-reference.md`, with decision records under
`docs/decisions/`. This is a documentation artifact — "verification" means reviewing it
against the spec's acceptance scenarios, not running code.

---

## Look up a mapping (US1)

1. Open `docs/architecture/doctype-mapping-reference.md`.
2. Find the ERPNext concept (e.g. "Item") in the matrix.
3. Read across: Retail Tower counterpart (`tenant_products`), owner of truth (DP2 for the
   product record; ERPNext for Item identity/accounting), status, and the DP2 citation.
4. Follow the citation into the DP2 repo to confirm the counterpart (US2 / SC-004).

## Check what's unresolved (US3)

1. Scan the matrix `Status` column for `Decision needed`.
2. For each, open the matching `docs/decisions/mapping-*.md`.
3. Read the question, options, and the **Sign-off** line — `signed` or `open`.
4. A planner uses the `Blocks` field to see which later spec (003–007) is gated.

## Verification checklist (maps to acceptance scenarios)

| Check | Expected | Maps to |
|-------|----------|---------|
| All concepts present | Company, Warehouse, Item, Barcode, UOM, Price List, Sale, Payment, Return each have a row + status | US1 / SC-001 |
| Counterpart + owner stated | each row names the DP2 counterpart and owner of truth | US1 / SC-002 |
| Citations locate | every row's DP2 citation can be opened and confirms the counterpart | US2 / SC-004 |
| Generic ERPNext addressing | ERPNext docs addressed via `{doctype, name}` only, no field names | US2 / FR-004 |
| Decisions have sign-off | every `Decision needed` row has a record with a sign-off line | US3 / SC-003 |
| Deferrals name owner | every `Deferred` concept names its later spec | US1 / FR-006 |
| Planner gating | unsigned decisions for a concept flagged as blocking that spec | US3 / SC-005 |

## Known statuses to expect (from research.md)

- **UOM** — Decision needed (no DP2 UOM master; free-text units). Record: `mapping-uom.md`.
- **Price List** — Resolved (reference only; DP2 amounts authoritative).
- **Payment Entry** — Deferred to spec 006 (no DP2 tender model).
- **Customer** — Deferred / ERPNext-owned (no DP2 Customer entity).

## Out of scope

No connector code, no DocType, no field-level ERPNext document construction. Those belong to
specs 003 (auth), 004 (product export), 005 (inventory), 006 (sales posting), 007 (tax).
This reference is the agreed vocabulary that unblocks them.
