# Implementation Plan: Data-Pulse Auth & API Policy

**Branch**: `003-data-pulse-auth-and-api-policy` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-data-pulse-auth-and-api-policy/spec.md`

## Summary

Produce a reviewed **auth & API policy** documenting the secure integration contract between
the connector and Data-Pulse-2: the connector authenticates **to** DP2 as a tenant-scoped
machine principal (it is the HTTP client — pull/ack), stores its bearer token securely,
acks outcomes idempotently, and logs with the DP2 server-side correlation identifier. The
policy **cites** DP2's authoritative contract and auth model — it does not re-derive them —
and is the security gate (G4) every later business-endpoint spec rides on. Documentation +
policy artifact only: no connector code (Principle VII).

## Technical Context

**Language/Version**: N/A — Markdown policy artifact. (Future connector client code is
Python/Frappe v15 per spec 001; not produced here.)

**Primary Dependencies**: Data-Pulse-2 backend (`C:\Users\user\Documents\GitHub\Data-Pulse-2`)
as the authoritative reference: the connector posting contract
(`packages/contracts/openapi/erpnext-connector/posting-feed.yaml`) and the token machinery
(`packages/auth/**`, `apps/api/src/auth/**`).

**Storage**: N/A for this feature. (The connector's at-rest token storage mechanism is a
later plan-phase decision; the policy states the *requirement*, not the mechanism.)

**Testing**: Reviewer verification against acceptance scenarios + DP2 citation locates. No
automated tests for a policy artifact. Staging authentication is a deferred validation
(no local bench; blocked on the DP2 connector-token-scope dependency).

**Target Platform**: N/A (policy document under `docs/`).

**Project Type**: Documentation / policy (single project).

**Performance Goals**: N/A.

**Constraints**: Connector→DP2 direction (authoritative contract); cite DP2, don't redefine
(FR-012, Principle I); generic `{doctype,name}` addressing (FR-004, Principle II); idempotent
ack + no duplicate posting (Principle IV); no secrets in logs/UI + correlation id (Principle
V, gate G4); docs-only (FR-011, Principle VII).

**Scale/Scope**: One auth & API policy document, plus a decision record for the DP2
connector-token-scope dependency. No data volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial evaluation (pre-design):**

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Data-Pulse-2 is the only orchestration boundary | ✅ Pass | Connector authenticates TO DP2 and pulls/acks; no path bypasses DP2; the policy cites DP2's contract as authoritative (FR-003, FR-012). |
| II. No ERPNext fork (connector stays thin) | ✅ Pass | ERPNext documents referenced only via generic `{doctype, name}` in the ack (FR-004); no ERPNext field names. |
| III. Additive & upgrade-safe changes | ✅ Pass (N/A) | Documentation only; no schema/migration. |
| IV. Idempotent mutations | ✅ Pass | The policy mandates idempotent ack (FR-005) and no-duplicate ERPNext posting on re-delivery (FR-006), keyed on source-system + external-id. This is the spec where Principle IV first applies. |
| V. Observable failures | ✅ Pass | The policy mandates a correlation identifier on pull/ack logs (FR-009) and a typed rejection taxonomy (FR-008). This is where Principle V first applies. |
| VI. Fiscal & stock truth is never hidden | ✅ Pass (N/A) | No fiscal/stock surfaces; tax passthrough (etaStatus) is deferred to spec 007. |
| VII. Spec-driven, contract-first delivery | ✅ Pass | This is the auth-contract policy itself; FR-011 forbids implementing endpoints; the auth model must be documented before business endpoints (specs 004+). |

**Result**: PASS — no violations. Complexity Tracking empty.

**Post-design re-evaluation (after Phase 1):** See [Post-Design Constitution Re-Check](#post-design-constitution-re-check).

## Project Structure

### Documentation (this feature)

```text
specs/003-data-pulse-auth-and-api-policy/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — authoritative DP2 citations + the 3 gap calls
├── data-model.md        # Phase 1 — Service Principal, Service Token, Work Item/Outcome (concept)
├── quickstart.md        # Phase 1 — how a reviewer/operator verifies the policy
├── spec.md              # Feature specification
└── checklists/
    └── requirements.md  # Spec quality checklist (16/16 pass)
```

*No `contracts/` directory: the connector↔DP2 interface contract already exists and is owned
by DP2 (`posting-feed.yaml`). This policy cites it. Emitting a contract here would create a
second source of truth (FR-012 / Principle I).*

### Source Code (repository root)

```text
docs/
├── decisions/
│   ├── data-pulse-auth-and-api-policy.md   # the auth & API policy (FR-001..FR-010, FR-012)
│   └── connector-token-scope.md            # decision record: DP2 connector-token-scope dependency
└── architecture/
    └── boundaries.md                       # (existing per README layout; referenced)
```

**Structure Decision**: The policy lives at `docs/decisions/data-pulse-auth-and-api-policy.md`
(an architecture/decision artifact per the README layout). The DP2 connector-token-scope gap
(spec Dependencies) gets its own decision record `docs/decisions/connector-token-scope.md`
with a sign-off line, mirroring the spec-002 decision-record pattern. Both Markdown; no code.

## Complexity Tracking

> No Constitution Check violations. No complexity to justify. (Section intentionally empty.)

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (data-model.md + quickstart.md; contracts/ skipped with reason):

- **Principle I (DP2 boundary)**: Confirmed — the policy cites DP2's contract/auth model;
  defines no connector-owned auth surface; connector is the client.
- **Principle II (no fork)**: Confirmed — ack references ERPNext docs only as `{doctype,name}`.
- **Principle IV (idempotent)**: Confirmed — idempotent ack + no-duplicate posting are
  first-class requirements with acceptance scenarios.
- **Principle V (observable)**: Confirmed — correlation-id logging + typed taxonomy required;
  no-secrets-in-logs is the G4 gate.
- **Principle VII (no implementation)**: Confirmed — policy + decision record only; no
  endpoints or token-handling code; gates specs 004+.

**Result**: PASS (post-design). No new violations. Ready for `/speckit-tasks`.
