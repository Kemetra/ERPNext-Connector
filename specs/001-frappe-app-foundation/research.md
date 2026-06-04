# Phase 0 Research: Frappe App Foundation

**Feature**: 001-frappe-app-foundation | **Date**: 2026-06-04

The Technical Context is almost entirely fixed by the Frappe/ERPNext framework and the
project's standing constraints (README + constitution + spec Assumptions), so there are no
open `NEEDS CLARIFICATION` items. One genuine design decision — deferred from `/speckit-clarify`
to plan time — is resolved here.

---

## Decision 1: Connector Settings as a Single DocType

**Decision**: Implement Connector Settings as a Frappe **Single DocType** (a site-wide
singleton), created as an empty placeholder with no functional fields.

**Rationale**:
- The spec requires exactly one configuration record ("a single Connector Settings record
  that can be opened" — FR-004, US2). A Single DocType *is* a singleton by definition, so
  reinstall/double-install cannot duplicate it (covers the reinstall edge case and
  Constitution Principle IV's "no duplicates" intent).
- Frappe's tenancy boundary is the **site** (each tenant = a separate site on the bench).
  A Single DocType is therefore inherently per-tenant with no `tenant_id` field, satisfying
  Constitution Principle I (tenant isolation) for free.
- It matches ERPNext's own convention: every `*-Settings` DocType (Selling Settings, Stock
  Settings, Accounts Settings, …) is a Single DocType. Following the host platform's
  pattern keeps the connector idiomatic and upgrade-safe (Principle II/III).

**Alternatives considered**:
- *Regular DocType with one enforced record*: rejected — requires custom uniqueness logic
  to prevent a second record, adding business logic to a no-logic scaffold (violates the
  proportionality/governance clause and Principle VII's spirit).
- *Site config / `site_config.json` keys*: rejected — not discoverable in the UI, fails
  US2's "operator can locate and open Connector Settings" acceptance test (SC-002).
- *Deferring any settings surface to spec 003*: rejected — the README scope for 001
  explicitly includes a "Connector Settings DocType placeholder"; the anchor must exist now
  so later specs attach to it without re-litigating where config lives.

---

## Decision 2: Version compatibility declared, not enforced

**Decision**: Pin the supported ERPNext/Frappe version (v15) in `pyproject.toml`
`required_apps`/metadata and document it; do **not** add install-time version-blocking logic.

**Rationale**: The spec's Edge Cases and Assumptions already commit to a documentation
stance ("the documented policy MUST state this is unsupported"). Install-time enforcement
would add logic to a no-logic scaffold. Frappe's `bench install-app` already surfaces gross
incompatibilities; an explicit policy doc covers the operator action.

**Alternatives considered**:
- *Hard version gate in `before_install` hook*: rejected — adds logic and a failure surface
  the foundation deliberately avoids; revisit only if staging install reveals a real need.

---

## Decision 3: No external contracts at the foundation

**Decision**: Do not produce a `contracts/` directory for this feature.

**Rationale**: The foundation exposes no external interface. Data-Pulse-2 authentication
and the request/response envelope are spec 003; product/inventory export surfaces are specs
004–005. The plan skill instructs skipping contracts for purely-internal scaffolding.
Emitting placeholder contracts would pre-commit interface decisions reserved for contract
review under Constitution Principle VII (contract-first delivery).

---

## Open items

None. All Technical Context fields are resolved; no `NEEDS CLARIFICATION` remains.
