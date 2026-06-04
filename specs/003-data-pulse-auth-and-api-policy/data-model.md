# Phase 1 Data Model: Data-Pulse Auth & API Policy

**Feature**: 003-data-pulse-auth-and-api-policy | **Date**: 2026-06-04

This feature produces a **policy document + decision record**, not stored data. No DocType,
schema, or migration (Principle VII). The "entities" below define the concepts the policy
describes; their canonical shapes are owned by Data-Pulse-2 and cited, not redefined
(Principle I).

---

## Entity: Connector Service Principal (DP2-owned, cited)

The tenant-scoped machine identity the connector uses to authenticate to DP2.

| Property | Value | Owner |
|----------|-------|-------|
| Identity | tenant-scoped machine principal | DP2 |
| Credential | opaque, revocable bearer token (`connectorBearer`) | DP2 issues |
| Scope source | tenant + store derived from the principal, never from the request body | DP2 |
| Scope value | a dedicated connector/machine scope — **does not exist in DP2 yet** (gap) | DP2 dependency |

**Concept-level only**: provisioning, hashing, revocation are DP2's. The policy cites them.

## Entity: Service Token (connector-side concern)

The secret the connector stores to authenticate to DP2.

| Aspect | Policy requirement | Owner |
|--------|--------------------|-------|
| At-rest storage | stored securely; raw value never retrievable in plaintext from logs/UI (FR-007) | connector (mechanism = plan phase) |
| Exposure | never logged, displayed, or in error messages (FR-008, gate G4) | connector |
| Server-side storage | DP2 stores only a SHA-256 hash, never the raw token; revocable | DP2 (cited) |
| Lifecycle | revoked token → connector calls refused (non-disclosing); operator re-auth state | DP2 revokes; connector surfaces |

## Entity: Posting Work Item / Outcome (DP2-owned, cited)

The unit pulled from DP2 and acked back. Shape owned by `posting-feed.yaml`; cited.

| Aspect | Value (cited) |
|--------|---------------|
| Pull | page of work items, cursor-based (`since` + `limit` 1–500) |
| Dedup identity | `sourceSystem + externalId` (wire idempotency anchor) |
| Ack idempotency | required `Idempotency-Key` header; same-outcome → replay; conflict → 409 |
| Outcome taxonomy | `posted` / `failed_transient` / `permanently_rejected` |
| Posted outcome | supplies ERPNext doc ref as `{doctype, name}` (generic, FR-004) |
| Rejection category | `validation` / `closed_period` / `unmapped_item` / `unmapped_account` / `other` |
| Correlation | DP2 server-side `request_id` (no wire correlation field) |

**Connector-side delta** (what the policy owns, not DP2):
- Client-side idempotency so a re-pulled work item does not create a duplicate ERPNext
  document (FR-006).
- Client-side bounded backoff retry against `failed_transient`; no blind retry of
  `permanently_rejected` (FR-010).
- Logging the `request_id` for end-to-end correlation (FR-009).

---

## Entity: Connector Token Scope Decision Record

A decision record (`docs/decisions/connector-token-scope.md`) capturing the DP2-side gap:
no dedicated connector/machine token scope exists yet.

| Field | Meaning |
|-------|---------|
| Question | Which DP2 token scope authenticates the connector machine principal? |
| Options | (a) DP2 adds a `connector`/`machine` scope; (b) reuse an existing scope (rejected — least-privilege); (c) per-tenant service account |
| Blocks | Staging authentication (SC-001) until DP2 provisions the scope |
| Sign-off | open until DP2 confirms the scope |

---

## Explicitly absent (by design — Principle VII / FR-011)

- No connector endpoint code, token-handling code, HTTP client, or retry implementation.
- No `contracts/` — the connector↔DP2 contract is owned by DP2 (`posting-feed.yaml`), cited.
- No invented correlation field (the wire has none; log the DP2 `request_id`).
