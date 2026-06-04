# Quickstart: Using & Verifying the Data-Pulse Auth & API Policy

**Feature**: 003-data-pulse-auth-and-api-policy | **Date**: 2026-06-04

How a reviewer/operator uses the policy once it exists at
`docs/decisions/data-pulse-auth-and-api-policy.md`, with the connector-token-scope decision
at `docs/decisions/connector-token-scope.md`. This is a policy artifact — "verification"
means reviewing it against the spec's acceptance scenarios, not running code. Staging
authentication is a deferred validation (no local bench; blocked on the DP2 token-scope
dependency).

---

## Read the policy (US1/US2/US3)

1. Open `docs/decisions/data-pulse-auth-and-api-policy.md`.
2. Confirm the **direction**: the connector authenticates TO Data-Pulse-2 (pull/ack client).
3. Read the **auth** rule: tenant-scoped machine principal, opaque revocable bearer token,
   scope from the principal (never the body).
4. Read the **idempotency** rule: required idempotency key on ack; `sourceSystem+externalId`
   dedup; no duplicate ERPNext posting on re-pull.
5. Read the **error taxonomy**: outcome (`posted`/`failed_transient`/`permanently_rejected`)
   and rejection categories.
6. Read the **secrets/correlation** rule: token never in logs/UI; log the DP2 `request_id`.
7. Each rule cites a Data-Pulse-2 source — follow the citation to confirm.

## Check the dependency (token scope)

1. Open `docs/decisions/connector-token-scope.md`.
2. Read the question, options, **Sign-off** line (open until DP2 provisions a connector scope).
3. Note it **blocks** staging authentication (SC-001), not the policy itself.

## Verification checklist (maps to acceptance scenarios)

| Check | Expected | Maps to |
|-------|----------|---------|
| Auth direction stated | connector → DP2 (client pulls/acks); DP2 makes no inbound calls | US1 / FR-003 |
| Machine principal + scope-from-principal | documented; no body-supplied tenant/store | US1 / FR-001/002 |
| Idempotent ack | required idempotency key; replay vs conflict behavior stated | US2 / FR-005 |
| No duplicate posting | client-side idempotency on `sourceSystem+externalId` | US2 / FR-006 |
| Token never exposed | rule present for logs, errors, and UI | US3 / FR-007/008 / G4 |
| Correlation id logged | connector logs the DP2 `request_id` (no invented field) | US3 / FR-009 |
| Citations locate | every cited DP2 path resolves and confirms the claim | FR-012 |
| Token-scope dependency recorded | decision record exists with sign-off + blocks SC-001 | Dependencies |
| Docs-only | no endpoints/token code produced | FR-011 / Principle VII |

## Deferred to staging (no local bench; DP2 dependency)

- `SC-001` (connector authenticates to DP2 and pulls a tenant-scoped feed) requires DP2 to
  provision a connector token scope AND a staging environment. Marked `⏳ BENCH/STAGING-VALIDATION`.

## Out of scope

No connector code, no HTTP client, no token-handling implementation, no business endpoints.
Those belong to specs 004 (product export), 005 (inventory), 006 (sales posting), 007 (tax).
This policy is the secure-channel contract those specs depend on (gate G4).
