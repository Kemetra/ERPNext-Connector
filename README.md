<div align="center">

<img src="docs/assets/brand/connector-logo.svg" alt="Retail Tower ERPNext Connector logo" width="120" height="120"/>

# Retail Tower ERPNext Connector

**The ERPNext-facing integration layer for Retail Tower OS — the only component allowed to touch ERPNext.**

Custom Frappe / ERPNext app that adapts ERPNext business documents, APIs, and configuration into
stable contracts consumed by Data-Pulse-2.

![Platform](https://img.shields.io/badge/platform-Frappe%20%2F%20ERPNext%20v15-0e7490)
![Boundary](https://img.shields.io/badge/boundary-Data--Pulse--2%20only-7c3aed)
![Status](https://img.shields.io/badge/status-foundation%20shipped%20%C2%B7%20003%20auth%20drafted-b45309)
![Mutation](https://img.shields.io/badge/ERP%20mutation-none%20yet-1e293b)
![License](https://img.shields.io/badge/license-internal-555)

</div>

---

## Purpose

Retail Tower OS uses ERPNext as its ERP, accounting, and inventory reference system — but ERPNext
does **not** replace the Retail Tower operational applications. This connector keeps the ERPNext
integration isolated, versioned, testable, and upgrade-safe.

The target integration rule is one direction, through one boundary:

```text
POS-Pulse             ──▶  Data-Pulse-2  ──▶  Retail Tower ERPNext Connector  ──▶  ERPNext / Frappe
Retail-Tower-Console  ──▶  Data-Pulse-2  ──▶  Retail Tower ERPNext Connector  ──▶  ERPNext / Frappe
ERPNext POS behavior  ──▶  Reference only
```

---

## 🔗 Synchronization — the only path to ERPNext

The connector is the **only** component allowed to touch ERPNext. It pulls sale postings from
Data-Pulse-2's posting feed (capture-UP), resolves each line to a confirmed ERPNext Item, posts,
and acks the outcome. It never forks ERPNext, copies its core, or exports catalog out of ERPNext
(reverse direction barred by G4).

<p align="center">
  <img src="docs/assets/architecture/retail-tower-sync-flow.svg" alt="Animated Retail Tower OS synchronization diagram, connector focus" width="100%"/>
</p>

```text
Data-Pulse-2  ──▶  Retail Tower ERPNext Connector  ──▶  ERPNext / Frappe
```

### Where the Connector sits — the full ecosystem

The diagram below places the connector within the complete five-repository Retail Tower OS
ecosystem: the **Retail Tower Orchestrator** control-plane band on top, governing the four
delivery repos beneath it. POS-Pulse and Retail-Tower-Console both synchronize through
Data-Pulse-2, the single contract boundary, which alone reaches ERPNext through this connector.

<p align="center">
  <img src="docs/assets/architecture/retail-tower-ecosystem.svg" alt="Retail Tower OS ecosystem diagram: an Orchestrator control-plane band over five repositories, with POS-Pulse and Retail-Tower-Console synchronizing through Data-Pulse-2 to the ERPNext Connector and ERPNext" width="100%"/>
</p>

<p align="center">
  <em>The ERPNext Connector — <strong>this repository</strong> — is the highlighted ERPNext-facing node
  (gold ★ THIS REPO badge). The diagram is a live animated SVG that honors
  <code>prefers-reduced-motion</code> for accessibility.</em>
</p>

Full detail (posting flow + sequence): [docs/architecture/synchronization.md](docs/architecture/synchronization.md) ·
Program control plane: [Retail-Tower-Orchestrator](https://github.com/ahmed-shaaban-94/Retail-Tower-Orchestrator).

---

## Repository Role

This repository owns the custom Frappe app `retail_tower_erpnext_connector`, responsible for:

- ERPNext / Frappe custom app foundation.
- Connector settings and integration configuration.
- Data-Pulse service authentication policy.
- ERPNext DocType mapping references.
- Product and price export surfaces.
- Inventory and warehouse export surfaces.
- Sales posting adapter.
- Tax and fiscal extension points.
- Upgrade and compatibility runbooks.

---

## Non-Goals

This repository must not become a fork of ERPNext.

Non-goals:

- Do not fork ERPNext.
- Do not copy ERPNext core code into this repository.
- Do not implement POS-Pulse cashier UI here.
- Do not allow POS-Pulse to call Frappe directly.
- Do not put Retail-Tower-Console backend logic here.
- Do not bypass Data-Pulse-2 contracts.
- Do not perform production ERPNext upgrades without staging gates.
- Do not implement sales, stock, or product mutations before the foundation and contract specs are approved.

---

## Architecture Boundary

Retail Tower OS keeps operational control in Data-Pulse-2. There is no direct path from
POS-Pulse or Retail-Tower-Console to ERPNext.

```text
POS-Pulse
  └─▶ Data-Pulse-2
        └─▶ Retail Tower ERPNext Connector
              └─▶ ERPNext / Frappe

Retail-Tower-Console
  └─▶ Data-Pulse-2
        └─▶ Retail Tower ERPNext Connector
              └─▶ ERPNext / Frappe

ERPNext POS behavior = Reference only.
```

---

## ERPNext POS Policy

ERPNext POS is used as a business-behavior reference only.

It may be used to study:

- POS Profile behavior.
- POS Invoice lifecycle.
- POS Closing Entry behavior.
- Payment method mapping.
- Warehouse and stock impact behavior.
- Return / refund behavior.
- Tax and fiscal behavior.

It must not become the production cashier terminal for Retail Tower OS.

---

## Initial Spec Roadmap

### 001 — Frappe App Foundation

Create the custom Frappe app foundation.

Scope:

- Frappe app scaffold.
- App metadata.
- Install policy.
- Version pinning policy.
- Connector Settings DocType placeholder.
- Local/staging setup notes.
- No ERP business mutation yet.

Exit criteria:

- App can be installed on a staging ERPNext site.
- App metadata is clear.
- No product, stock, or sales mutation exists.
- Upgrade policy is documented.

### 002 — DocType Mapping Reference

Document how ERPNext concepts map to Retail Tower concepts.

Mapping areas:

- Company ↔ Tenant.
- Warehouse ↔ Store / Branch.
- Item ↔ Product.
- Barcode ↔ Product alias / scan code.
- UOM ↔ Retail selling unit.
- Price List ↔ Retail price source.
- POS Invoice / Sales Invoice ↔ Retail sale.
- Payment Entry ↔ Tender settlement.
- Return Invoice ↔ Refund / return flow.

Exit criteria:

- Mapping matrix is reviewed.
- Ambiguous mappings are recorded as decisions.
- No implementation starts before required decisions are signed.

### 003 — Data-Pulse Auth and API Policy

Define the secure integration contract between Data-Pulse-2 and this connector.

Scope:

- Service authentication model.
- Token storage policy.
- IP restriction policy if applicable.
- Request/response envelope.
- Error taxonomy.
- Idempotency requirements.
- Correlation ID requirements.
- Rate-limit and retry policy.

Exit criteria:

- Data-Pulse can authenticate to the connector in staging.
- Secrets are not exposed in logs or UI.
- Auth model is documented before business endpoints are implemented.

### 004 — Product and Price Export

Expose ERPNext product and pricing information to Data-Pulse.

Scope:

- Item export.
- Barcode export.
- UOM export.
- Price List export.
- Active/inactive item state.
- Product update detection.
- Data-Pulse pull or push strategy.

Exit criteria:

- Data-Pulse can build a canonical catalog from ERPNext data.
- Missing price and inactive product states are explicit.
- POS-Pulse still receives catalog through Data-Pulse only.

### 005 — Inventory Export and Reservation

Expose ERPNext warehouse stock information safely.

Scope:

- Warehouse/store mapping.
- Stock snapshot export.
- Stock availability policy.
- Reservation/projection policy if approved.
- Stock reconciliation references.
- Stale data handling.

Exit criteria:

- Data-Pulse can show branch stock availability.
- Stale stock is visible.
- No direct POS stock mutation exists.
- Stock impact model is signed before mutation behavior.

### 006 — Sales Posting Adapter

Create ERPNext sales documents from validated Data-Pulse sale commands.

Scope:

- POS Invoice or Sales Invoice creation.
- Payment method mapping.
- ERP reference persistence.
- Idempotency protection.
- Retry-safe posting.
- Failure classification.
- Posting status response.

Exit criteria:

- Same sale replay does not create duplicate ERP documents.
- Failed posting is repairable without modifying the original sale fact.
- ERP document reference is returned to Data-Pulse.

### 007 — Tax and Fiscal Fields Egypt

Support tax and fiscal extension points required for Egyptian retail operations.

Scope:

- VAT field mapping.
- Tax category mapping.
- Receipt/invoice fiscal fields.
- Tax total validation.
- Regional compliance extension points.
- Golden fiscal test fixtures.

Exit criteria:

- Receipt tax equals Data-Pulse sale tax equals ERP invoice tax.
- Fiscal fields are documented.
- Customer-facing production is blocked until the fiscal gate passes.

### 008 — Upgrade and Compatibility Runbook

Document safe upgrade and compatibility rules.

Scope:

- ERPNext version pinning.
- Frappe version pinning.
- Staging upgrade workflow.
- Backup and restore steps.
- Connector regression checklist.
- Rollback policy.
- Compatibility matrix.

Exit criteria:

- Staging upgrade path is documented.
- Backup/restore is rehearsed.
- Connector regression checks are defined.
- Production upgrades require explicit approval gates.

---

## Delivery Waves

| Wave | Purpose | Connector Responsibility |
|---:|---|---|
| 0 | Governance and truth reconciliation | Confirm repo name, app name, and boundaries |
| 1 | ERPNext reference lab | Support ERPNext behavior mapping |
| 2 | Connector skeleton and secure channel | Create custom app foundation and auth path |
| 3 | Product/catalog source of truth | Export product, barcode, UOM, and pricing data |
| 4 | Inventory and stock truth | Export warehouse/store stock information |
| 5 | POS sale sync and ERP posting | Create ERP sales documents safely |
| 6 | VAT/fiscal hardening | Support tax and fiscal fields |
| 7 | Console operational UI | Provide status/errors to Data-Pulse for Console |
| 8 | Returns, refunds, shifts, cash control | Support return and closing behavior |
| 9 | Pilot and rollout | Support staging, backup, rollback, and regression |

---

## Quality Gates

| Gate | Name | Connector Evidence |
|---|---|---|
| G1 | Reference sign-off | ERPNext behavior map and DocType mapping reviewed |
| G2 | Contract gate | Data-Pulse connector contract approved |
| G3 | Migration gate | Additive migrations and rollback notes reviewed |
| G4 | Security gate | Auth, token storage, and tenant isolation verified |
| G5 | Idempotency gate | Replay does not duplicate ERP documents |
| G6 | Tax/fiscal gate | Tax totals match across POS, Data-Pulse, and ERPNext |
| G7 | Observability gate | Failures, retries, logs, and correlation IDs available |
| G8 | Upgrade gate | Staging upgrade and regression checklist passed |
| G9 | Pilot gate | One-branch pilot completed with rollback rehearsal |

---

## Development Principles

- Keep the connector small and explicit.
- Treat ERPNext as the ERP/accounting/inventory backend.
- Treat Data-Pulse-2 as the only Retail Tower orchestration boundary.
- Keep POS-Pulse isolated from Frappe.
- Prefer additive changes.
- Preserve auditability.
- Make every mutation idempotent.
- Make every failure observable.
- Never hide tax or stock uncertainty.
- Upgrade through staging, never directly in production.

---

## Suggested Initial Repository Structure

The target docs-and-app layout (some entries are planned, not all present yet):

```text
.
├── README.md
├── docs/
│   ├── architecture/
│   │   ├── boundaries.md
│   │   └── doctype-mapping-reference.md
│   ├── decisions/
│   │   ├── posting-model.md
│   │   ├── stock-impact-model.md
│   │   ├── tax-fiscal-model.md
│   │   └── version-pin-upgrade-policy.md
│   ├── runbooks/
│   │   ├── staging-install.md
│   │   ├── backup-restore.md
│   │   └── upgrade-compatibility.md
│   └── specs/
│       ├── 001-frappe-app-foundation.md
│       ├── 002-doctype-mapping-reference.md
│       ├── 003-data-pulse-auth-and-api-policy.md
│       ├── 004-product-and-price-export.md
│       ├── 005-inventory-export-and-reservation.md
│       ├── 006-sales-posting-adapter.md
│       ├── 007-tax-and-fiscal-fields-egypt.md
│       └── 008-upgrade-and-compatibility-runbook.md
└── retail_tower_erpnext_connector/
    └── README.md
```

---

## Current Status

**Spec 001 — Frappe App Foundation: implemented.** The custom Frappe app
`retail_tower_erpnext_connector` is scaffolded with app metadata, a `Connector Settings`
Single DocType placeholder, foundation tests, and install/version-pin/upgrade documentation.
No product, stock, price, or sales mutation exists, and ERPNext is not forked.

Built via spec-driven development (`.specify/`): see the constitution at
`.specify/memory/constitution.md` and the 001 artifacts under
`specs/001-frappe-app-foundation/` (spec → plan → tasks → analyze).

Staging install: see `docs/runbooks/staging-install.md`. Bench-validation steps (install,
verify, `run-tests`) run on a staging ERPNext v15 bench.

**Spec 002 — DocType Mapping Reference: drafted.** The ERPNext ↔ Retail Tower mapping matrix
is at [`docs/architecture/doctype-mapping-reference.md`](docs/architecture/doctype-mapping-reference.md).
It cites Data-Pulse-2 as authoritative for the Retail Tower side (it does not re-derive the
mapping) and records ambiguous mappings as decision records under `docs/decisions/`
(`mapping-uom.md`, `mapping-customer.md`) with open sign-offs that gate later specs.

**Spec 003 — Data-Pulse Auth & API Policy: drafted.** The connector↔Data-Pulse-2 secure-channel
policy is at [`docs/decisions/data-pulse-auth-and-api-policy.md`](docs/decisions/data-pulse-auth-and-api-policy.md):
the connector authenticates **to** Data-Pulse-2 as a tenant-scoped machine principal and is the
HTTP client (pull/ack); idempotent ack + no-duplicate posting; no secrets in logs + correlation
via the DP2 `request_id`. It is the **security gate (G4)** that specs 004+ ride on. An open
dependency (`docs/decisions/connector-token-scope.md`) tracks that DP2 must provision a dedicated
connector token scope before staging authentication.

**Next work item:** `004-product-and-price-export`.

Do not implement catalog, inventory, sales posting, or tax mutation before the relevant
connector contract is reviewed (constitution Principle VII). **Gate status before 004+:** the
003 auth policy (G4) is in place; the UOM, Customer, and connector-token-scope decisions are
**signed** (all Option A, 2026-06-04). Remaining dependency: DP2 must still *provision* the
connector token scope before staging authentication (SC-001) — the decision is signed, the
delivery is pending.

---

## Related Repositories

| Repository | Role |
|---|---|
| [Retail-Tower-Orchestrator](https://github.com/ahmed-shaaban-94/Retail-Tower-Orchestrator) | Docs-only cross-repo control plane (gates, roadmap, status). |
| Data-Pulse-2 | Retail Tower backend, contracts, orchestration, and APIs. |
| POS-Pulse | Windows offline-capable cashier terminal. |
| Retail-Tower-Console | Frontend-only admin and operations console. |
| **Retail-Tower-ERPNext-Connector** | **This repository** — custom Frappe / ERPNext connector. |

---

## License

Private / internal Retail Tower OS project unless stated otherwise.
