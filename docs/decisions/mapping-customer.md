# Decision: Customer Mapping (ERPNext Customer for Retail Tower sales)

**Spec**: 002 — DocType Mapping Reference | **Status**: 🔴 OPEN | **Date raised**: 2026-06-04
**Blocks**: spec 006 (sales posting)

## Question

ERPNext Sales/POS Invoices require a **Customer**. Data-Pulse-2 has **no Customer entity** —
Retail Tower is walk-in retail and DP2 sales carry no customer reference (confirmed by the
DP2 survey; no schema file models a customer).

**When the connector posts a Retail Tower sale to ERPNext, which Customer does it use, and
who owns that decision?**

## Context (cited)

- DP2 `sales` carries no customer field: `packages/db/src/schema/sales/sales.ts`.
- The DP2 connector contract's `Sale` projection
  (`packages/contracts/openapi/erpnext-connector/posting-feed.yaml`) carries no customer.
- ERPNext POS Profiles typically define a default/walk-in customer for cash sales.

## Options

| # | Option | Implication |
|---|--------|-------------|
| A | **Use a configured default "walk-in" Customer per ERPNext site/POS Profile; the connector references it, ERPNext owns it.** | Matches ERPNext POS conventions; no customer data flows from DP2. Connector Settings (or a later config) holds the default Customer name. ERPNext-owned, connector-referenced. |
| B | DP2 starts modeling customers and passes a customer reference on the wire. | Out of connector scope; blocks on a DP2 change; unnecessary for walk-in retail. |
| C | Connector creates a Customer per sale. | Pollutes ERPNext with throwaway customers; rejected. |

## Recommendation

**Option A** — a configured default walk-in Customer, owned by ERPNext (per POS Profile),
referenced by the connector at posting time. No customer identity flows from DP2; the
connector treats Customer as ERPNext-owned configuration. This keeps DP2 unchanged
(Principle I) and matches ERPNext POS behavior.

## Sign-off

- [ ] **Decision signed** — by: ________________  date: __________
- Until signed, spec 006 MUST NOT implement Customer handling for posting.
