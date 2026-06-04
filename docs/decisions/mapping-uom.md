# Decision: UOM Mapping (ERPNext UOM ↔ Retail Tower unit)

**Spec**: 002 — DocType Mapping Reference | **Status**: 🔴 OPEN | **Date raised**: 2026-06-04
**Blocks**: spec 004 (product export), spec 006 (sales posting)

## Question

ERPNext models Unit of Measure as a first-class **UOM** master (with conversion factors per
Item). Data-Pulse-2 has **no UOM master entity** — the unit is a free-text string on the
sale line (`sale_lines.unit`) and on inventory (`stock_movements.stocking_unit`). DP2 itself
records this as an open question (013 OQ-3).

**How should the connector reconcile Data-Pulse-2's free-text unit with ERPNext's UOM when
posting sales and exporting products — and which side owns the canonical unit?**

## Context (cited)

- DP2 free-text unit: `packages/db/src/schema/sales/sale-lines.ts` (`unit text NOT NULL`),
  `packages/db/src/schema/inventory/stock-movements.ts` (`stocking_unit text NOT NULL`).
- DP2 enforces one distinct stocking unit per `(store, product)` (migration `0016`), so the
  free-text value is *consistent per product* even without a master.
- ERPNext requires a valid UOM (and Item-level UOM conversions) on Sales/POS Invoice lines.

## Options

| # | Option | Implication |
|---|--------|-------------|
| A | **Connector maps each distinct DP2 free-text unit string to an ERPNext UOM via a small mapping table/config; unmapped units are a posting error (`unmapped` outcome).** | Keeps DP2 free-text; pushes the canonicalization to the connector boundary. Requires a maintained unit→UOM map. Fails closed (no silent guess) — aligns with constitution Principle VI (no hidden uncertainty). |
| B | DP2 adds a UOM master / normalizes units upstream; connector just passes through. | Cleaner long-term, but changes DP2 (out of connector scope) and blocks on a DP2 change. |
| C | Assume DP2 unit strings already equal ERPNext UOM names (string identity); error only on mismatch. | Lowest effort; brittle — any naming drift silently fails or mis-posts. Weakest on Principle VI. |

## Recommendation

**Option A** — a connector-side unit→ERPNext-UOM mapping with explicit `unmapped` failure,
surfaced via the connector contract's existing rejection category. It keeps DP2 authoritative
for the *value*, keeps ERPNext authoritative for the *UOM master*, and never silently guesses
(Principle VI). Revisit Option B if DP2 later introduces a UOM master.

## Sign-off

- [ ] **Decision signed** — by: ________________  date: __________
- Until signed, specs 004 and 006 MUST NOT implement unit handling.
