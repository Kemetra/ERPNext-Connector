<!--
SYNC IMPACT REPORT
==================
Version change: (none / template) → 1.0.0
Bump rationale: Initial ratification of the project constitution (new document,
  no prior version). MAJOR baseline established.

Principles defined (7):
  I.   Data-Pulse-2 Is the Only Orchestration Boundary
  II.  No ERPNext Fork (Connector Stays Thin)
  III. Additive & Upgrade-Safe Changes
  IV.  Idempotent Mutations
  V.   Observable Failures
  VI.  Fiscal & Stock Truth Is Never Hidden
  VII. Spec-Driven, Contract-First Delivery

Sections defined:
  - Security & Compliance Requirements (Section 2)
  - Development Workflow & Quality Gates (Section 3)
  - Governance

Added sections: All (initial creation).
Removed sections: None.

Templates requiring updates:
  - .specify/templates/plan-template.md   ✅ reviewed — "Constitution Check" gate
        reads principles dynamically at plan-time; no edit needed.
  - .specify/templates/spec-template.md   ✅ reviewed — no constitution-specific
        mandatory sections to add; aligned.
  - .specify/templates/tasks-template.md  ✅ reviewed — task categories support
        observability/idempotency/test tasks driven by principles; no edit needed.

Follow-up TODOs: None. Ratification date set to initial adoption (2026-06-04).
-->

# Retail Tower ERPNext Connector Constitution

## Core Principles

### I. Data-Pulse-2 Is the Only Orchestration Boundary

POS-Pulse and Retail-Tower-Console MUST NOT call Frappe or ERPNext directly. All
operational traffic into this connector MUST flow through Data-Pulse-2. This connector
MUST NOT contain POS-Pulse cashier UI or Retail-Tower-Console backend logic.

**Rationale**: Retail Tower OS keeps operational control in Data-Pulse-2. A single
orchestration boundary preserves tenant isolation, keeps contracts auditable, and
prevents ERPNext from becoming a hidden coupling point for the rest of the platform.

### II. No ERPNext Fork (Connector Stays Thin)

This repository MUST remain a custom Frappe app (`retail_tower_erpnext_connector`) and
MUST NOT fork ERPNext or copy ERPNext/Frappe core code into the repository. ERPNext is
treated as the ERP, accounting, and inventory backend — referenced, not reimplemented.
ERPNext POS behavior MAY be studied as a reference but MUST NOT become the production
cashier terminal.

**Rationale**: A thin connector stays upgrade-safe and testable. Copying core code
creates a maintenance fork that silently diverges from upstream and breaks on upgrade.

### III. Additive & Upgrade-Safe Changes

Changes MUST be additive by default. Schema and DocType changes MUST ship with rollback
notes and MUST pass the migration gate (G3). ERPNext and Frappe versions MUST be pinned,
and production upgrades MUST go through staging with a rehearsed backup/restore — never
applied directly in production.

**Rationale**: ERPNext upgrades and tenant data are high-blast-radius. Additive,
reversible, staged change is the only safe path for a production accounting backend.

### IV. Idempotent Mutations

Every ERP mutation (sales posting, stock impact, payment settlement) MUST be idempotent.
Replaying the same sale or command MUST NOT create duplicate ERP documents. Each request
MUST carry an idempotency key, and the ERP document reference MUST be returned to
Data-Pulse-2. Failed postings MUST be repairable without modifying the original sale fact.

**Rationale**: Network retries and at-least-once delivery are inevitable across the
Data-Pulse → connector → ERPNext chain. Idempotency is what keeps the ledger correct.

### V. Observable Failures

Every failure MUST be observable. Operations MUST emit structured logs, a correlation ID
traceable end-to-end from Data-Pulse-2, retry status, and a typed error taxonomy.
Secrets, tokens, and credentials MUST NOT appear in logs, error messages, or UI.

**Rationale**: A connector that fails silently is unoperatable. Correlation IDs and a
failure taxonomy let operators repair postings without guessing, and satisfy gate G7.

### VI. Fiscal & Stock Truth Is Never Hidden

Tax and stock uncertainty MUST be surfaced explicitly, never masked. Tax totals MUST
reconcile across POS-Pulse, Data-Pulse-2, and ERPNext (receipt tax = sale tax = ERP
invoice tax). Stale or missing stock and missing-price/inactive-product states MUST be
visible to consumers, not silently defaulted.

**Rationale**: Hidden fiscal or stock discrepancies become compliance failures and
customer-trust failures. Gate G6 blocks customer-facing production until tax reconciles.

### VII. Spec-Driven, Contract-First Delivery

No catalog, inventory, sales-posting, or tax mutation MAY be implemented before the
foundation and the relevant contract specification are reviewed and signed. Work proceeds
through the Spec Kit flow (specify → plan → tasks → implement) and the quality gates in
Section 3. Ambiguous mappings MUST be recorded as signed decisions before implementation.

**Rationale**: This is a high-stakes integration layer. Contract-first delivery prevents
expensive rework and ensures every mutation traces back to an approved specification.

## Security & Compliance Requirements

- **Authentication & secrets (Gate G4)**: Data-Pulse-2 MUST authenticate to the connector
  using a defined service-auth model. Tokens MUST be stored securely and MUST NOT be
  exposed in logs or UI. Tenant isolation MUST be verified for every data surface.
- **Transport & access**: IP restrictions and rate-limit/retry policy MUST be defined
  before business endpoints are implemented. Requests MUST use the agreed request/response
  envelope and carry correlation IDs.
- **Egyptian tax & fiscal compliance**: VAT and tax-category mappings, receipt/invoice
  fiscal fields, and tax-total validation MUST be implemented with golden fiscal test
  fixtures. Customer-facing production is blocked until the fiscal gate (G6) passes.
- **Auditability**: Every mutation MUST be auditable — who/what/when, the originating
  Data-Pulse correlation ID, and the resulting ERP document reference.

## Development Workflow & Quality Gates

Delivery follows the spec roadmap (001–008) and delivery waves 0–9 defined in `README.md`.
Each increment MUST clear the applicable quality gates before advancing:

| Gate | Name | Evidence required |
|------|------|-------------------|
| G1 | Reference sign-off | ERPNext behavior map and DocType mapping reviewed |
| G2 | Contract gate | Data-Pulse connector contract approved |
| G3 | Migration gate | Additive migrations and rollback notes reviewed |
| G4 | Security gate | Auth, token storage, and tenant isolation verified |
| G5 | Idempotency gate | Replay does not duplicate ERP documents |
| G6 | Tax/fiscal gate | Tax totals match across POS, Data-Pulse, and ERPNext |
| G7 | Observability gate | Failures, retries, logs, and correlation IDs available |
| G8 | Upgrade gate | Staging upgrade and regression checklist passed |
| G9 | Pilot gate | One-branch pilot completed with rollback rehearsal |

Workflow rules:

- The connector MUST stay small and explicit; complexity MUST be justified against a
  simpler rejected alternative.
- The recommended first work item is `001-frappe-app-foundation`; no business mutation
  ships before the foundation and connector contract are reviewed.
- Each spec proceeds through `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`, with `/speckit-clarify`, `/speckit-analyze`, and
  `/speckit-checklist` used to de-risk ambiguous or high-stakes work.

## Governance

This constitution supersedes other practices for this repository. Where it conflicts with
ad-hoc convenience, this document wins.

- **Amendments** MUST be proposed as a documented change, reviewed, and accompanied by a
  migration/propagation note for any dependent template or runbook.
- **Versioning policy** (semantic):
  - MAJOR — backward-incompatible governance or principle removal/redefinition.
  - MINOR — a new principle or section is added, or guidance is materially expanded.
  - PATCH — clarifications, wording, or non-semantic refinements.
- **Compliance review**: All PRs and reviews MUST verify compliance with these principles
  and the applicable quality gates. Violations block merge until resolved or justified in
  the plan's Complexity Tracking section.
- **Runtime guidance**: Use `README.md` and `CLAUDE.md` for day-to-day development
  guidance; this constitution governs the non-negotiable rules they operate within.

**Version**: 1.0.0 | **Ratified**: 2026-06-04 | **Last Amended**: 2026-06-04
