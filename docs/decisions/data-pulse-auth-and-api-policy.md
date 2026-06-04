# Data-Pulse Auth & API Policy

**Status**: Draft — 2026-06-04
**Spec**: [003-data-pulse-auth-and-api-policy](../../specs/003-data-pulse-auth-and-api-policy/spec.md)
**Gates**: G4 (security), G5 (idempotency), G7 (observability)

---

## Purpose

This document is the security gate (G4) that every later business-endpoint spec (004+) rides
on. It records the auth model, API contract, idempotency discipline, error taxonomy, and
observability rules governing the connector's integration with Data-Pulse-2. No connector
code or endpoint is produced here (FR-011, Principle VII).

---

## 1. Sources & Precedence

Data-Pulse-2 is the single authoritative source for:

- the connector↔DP2 wire contract
- the token issuance, hashing, and revocation model
- the request/response envelope shapes
- the outcome taxonomy, rejection categories, and idempotency mechanism
- the dedup key and pagination semantics

This policy **cites** those sources; it does not redefine them (FR-012, Principle I).
Code and contracts outrank prose: where any description here conflicts with a DP2 source
file, the source file wins.

The connector-side delta this policy **owns** is: secure at-rest storage of the connector's
copy of the service token; client-side retry/backoff discipline; client-side idempotency so a
re-pulled work item does not create a duplicate ERPNext document; and logging the DP2
server-side `request_id` for correlation.

**Precedence order** (highest to lowest):

1. DP2 OpenAPI contract:
   `packages/contracts/openapi/erpnext-connector/posting-feed.yaml`
2. DP2 auth machinery (see §4 below)
3. This policy document
4. DP2 prose specs and decision records

---

## 2. Direction — Connector Is the HTTP Client

The connector is the HTTP **client**. Data-Pulse-2 makes **no** outbound calls to the
connector. Every data and command path crosses the DP2 boundary (Principle I, FR-003).

The authoritative contract defines exactly two connector-facing operations, both with the
connector as caller:

| Operation | Method + Path | Auth |
|-----------|--------------|------|
| `connectorPullPostings` | `GET /api/connector/v1/erpnext/postings` | `connectorBearer` |
| `connectorAckOutcome` | `POST /api/connector/v1/erpnext/postings/{workItemRef}/outcome` | `connectorBearer` |

**Source**: `packages/contracts/openapi/erpnext-connector/posting-feed.yaml`,
operationIds `connectorPullPostings` and `connectorAckOutcome`.

The README arrow "DP2 → connector → ERPNext" describes authority and data-origin direction,
not HTTP direction. If a connector-exposed inbound surface were ever genuinely needed, that
would be a distinct feature with its own DP2-side contract — no such surface exists.

**Reconciliation with the constitution (Gate G4).** The project constitution
(`.specify/memory/constitution.md`, Section 2) phrases G4 as _"Data-Pulse-2 MUST authenticate
to the connector using a defined service-auth model."_ This describes the same
**authority/data-origin direction** as the README arrow — DP2 is the upstream authority whose
operational traffic the connector serves — **not** the HTTP/transport direction. The
authoritative wire reality, fixed by the only contract that exists
(`posting-feed.yaml`), is that the **connector is the HTTP client** (it pulls from and acks to
DP2 via `connectorBearer`); DP2 makes no outbound calls. Per standing-rules §0 the constitution
is supreme, so this policy does **not** reverse the wire direction to match the G4 prose;
instead it flags that the constitution's G4 wording is ambiguous between authority and
transport direction and **warrants a PATCH amendment** to disambiguate (e.g. "the connector
authenticates *to* Data-Pulse-2 as a tenant-scoped machine principal"). This document is the
artifact that surfaces that ambiguity; the amendment is tracked as follow-up, separate from
this spec.

---

## 3. Authentication — Tenant-Scoped Machine Principal

### 3.1 Token model (DP2-owned, cited)

The connector authenticates to DP2 as a dedicated, **tenant-scoped, revocable machine
principal** using an opaque service bearer token named `connectorBearer` in the contract
(FR-001). The security scheme is declared as `type: http, scheme: bearer` in
`posting-feed.yaml` (`components/securitySchemes/connectorBearer`):

> _"OPAQUE, REVOCABLE service bearer token … NOT a Clerk JWT (`clerkJwt`) and NOT a human
> cookie session. The connector authenticates as a dedicated, tenant-scoped, revocable
> MACHINE principal."_

Token generation, hashing, and revocation are DP2-owned:

- **Generation**: `generateRawToken()` in
  `packages/auth/src/tokens.ts` — 32 cryptographically random bytes, URL-safe base64.
  The raw value is shown to the issuer exactly once and never persisted server-side.
- **Hashing**: `hashToken()` in `packages/auth/src/tokens.ts` — SHA-256 of the raw token;
  stored in `auth_tokens.token_hash` (BYTEA). The raw token is never written to the DB.
- **Comparison**: `tokenHashesEqual()` in `packages/auth/src/tokens.ts` — constant-time
  (`timingSafeEqual`) comparison of hash buffers, preventing timing-oracle attacks.
- **Branded types**: `RawToken` and `TokenHash` in `packages/auth/src/types.ts` — nominal
  compile-time guards that make it a type error to persist a `RawToken` where a `TokenHash`
  is expected.
- **Issuance / lookup**: `AuthTokenRepository.issue()` and `findActiveByRawToken()` in
  `apps/api/src/auth/auth-token.repository.ts` — both take a raw token and hash it internally,
  so callers never pass a raw secret as a SQL parameter. `AuthTokenRepository.revoke()`
  operates on a token **id** (not a raw token) and hashes nothing, so the connector never
  needs to present a raw secret to revoke.

### 3.2 Scope derivation (FR-002)

Tenant and store scope are derived from the authenticated principal at the DP2 API edge,
never from the request body. This is enforced in two places in DP2:

- `TenantContextGuard.resolveToken()` in
  `apps/api/src/context/tenant-context.guard.ts` — for `kind === "token"` principals,
  reads `principal.tenantId` and `principal.storeId` from the token row baked at issuance.
- `OutcomeAckRequest` in `posting-feed.yaml` — declared `additionalProperties: false`;
  body-supplied tenant/store/actor fields are rejected as validation failures.

### 3.3 Existing token scopes (gap)

The current `AuthTokenScope` type in `packages/auth/src/types.ts` defines two values:
`"dashboard_api"` and `"pos"`. A dedicated connector/machine-principal scope does not yet
exist in DP2. This is a tracked external dependency that blocks staging authentication
(SC-001). See decision record:
[`docs/decisions/connector-token-scope.md`](./connector-token-scope.md)

---

## 4. Idempotency & Dedup

### 4.1 Ack idempotency (FR-005, Principle IV)

The `connectorAckOutcome` operation is marked `x-idempotency: required` in
`posting-feed.yaml`. The `Idempotency-Key` header is **required** on every ack call
(parameter `IdempotencyKey` in `posting-feed.yaml`). The DP2 idempotency mechanism is keyed
on `(method, route, clientId = connector principal, key)`:

- **Same outcome, same key** → idempotent 200 replay; `Idempotent-Replayed: true` header
  returned; no second recording. A duplicate `posted` echoes the existing `documentRef`.
- **Different outcome, same key** → 409 `idempotency_key_conflict`; the original outcome
  stands.

**Source**: `posting-feed.yaml`, operationId `connectorAckOutcome`, parameter
`IdempotencyKey`, and response `Conflict` (`idempotency_key_conflict`).

### 4.2 Wire dedup (FR-006, Principle IV)

Each `PostingWorkItem` carries a stable dedup identity: `sourceSystem + externalId`
(`posting-feed.yaml`, schema `PostingWorkItem`). These fields form the anchor the connector
uses to map a work item to a deterministic ERPNext document — the same pair resolves to the
same document on retry (obligation O-3 in `posting-feed.yaml`).

**Connector obligation**: when the same work item is delivered more than once (at-least-once
delivery), the connector MUST NOT create a duplicate ERPNext document. Client-side idempotency
keyed on `sourceSystem + externalId` is the connector's responsibility; DP2 guarantees
at-most-once outcome recording on its side via the ack idempotency mechanism above.

### 4.3 Stale-cursor re-baseline

A stale or unservable `since` cursor returns 409 `snapshot_required`
(`posting-feed.yaml`, response `SnapshotRequired`). The connector MUST re-baseline by pulling
from the start (omit `since`). Silently dropping work items on a stale cursor is not
permitted.

---

## 5. Error Taxonomy

### 5.1 Outcome enum (FR-004, FR-010)

`OutcomeAckRequest.outcome` in `posting-feed.yaml` is a closed enum:

| Value | Meaning | Connector obligation |
|-------|---------|---------------------|
| `posted` | Submitted to ERPNext. | Supply `documentRef` as `{doctype, name}`. |
| `failed_transient` | Retryable failure. | DP2 re-offers the work item; connector uses bounded backoff (see §5.3). |
| `permanently_rejected` | Non-retryable. | Supply `reason.category` from the rejection taxonomy; do not retry. DP2 dead-letters and raises a reconciliation flag. |

### 5.2 Rejection categories (FR-008)

`RejectionReason.category` in `posting-feed.yaml` is a closed enum:

| Category | Meaning |
|----------|---------|
| `validation` | The work item's payload is structurally invalid for ERPNext. |
| `closed_period` | The target fiscal period is closed. |
| `unmapped_item` | A product/item in the sale has no ERPNext mapping. |
| `unmapped_account` | A required account has no ERPNext mapping. |
| `other` | Any other permanent rejection cause. |

`RejectionReason.message` carries a human-readable explanation (max 1000 chars). It MUST NOT
contain credentials, token values, or sensitive ERPNext internals (FR-008, Principle V).

**Source**: `posting-feed.yaml`, schema `RejectionReason`.

### 5.3 Retry discipline (FR-010)

- `failed_transient` → DP2 re-offers the work item on the next pull; the connector uses a
  **bounded backoff** before the next pull cycle. DP2 enforces its own retry
  budget; the connector must not exhaust it by tight-looping.
- `permanently_rejected` → no blind retry. Submitting the same work item again without
  operator intervention is prohibited; the connector surfaces the rejection for operator
  action.
- 409 `idempotency_key_conflict` → deterministic, no retry; the ack must be corrected first.
- 409 `snapshot_required` → re-baseline, not a transient failure.

---

## 6. Posted-Outcome — ERPNext Document Reference (FR-004, Principle II)

When `outcome = posted`, the connector supplies the resulting ERPNext document reference as a
`documentRef` field of type `ErpnextDocumentRef`:

```
ErpnextDocumentRef:
  doctype: string   # e.g. "Sales Invoice"
  name:    string   # ERPNext primary key / document name
```

The reference addresses the ERPNext document **generically** — doctype + name only.
Field-level ERPNext internals are never included in the DP2-facing contract
(Principle II, obligation O-6 in `posting-feed.yaml`). An ERPNext v15→v16 change alters
the connector's internal mapping, not this wire shape.

**Source**: `posting-feed.yaml`, schema `ErpnextDocumentRef`; `OutcomeAckRequest.documentRef`
(required when `outcome = posted`).

---

## 7. Secrets & Correlation (FR-007, FR-008, FR-009, Principle V)

### 7.1 Token storage (FR-007, Gate G4)

The connector stores its copy of the raw `connectorBearer` token securely at rest. The raw
value MUST NOT be retrievable in plaintext from logs, error messages, or the operator UI.
The at-rest storage mechanism is a plan-phase implementation decision for the connector; this
policy states the requirement.

The DP2-side storage discipline is authoritative: DP2 stores only a SHA-256 hash
(`hashToken()` in `packages/auth/src/tokens.ts`; `AuthTokenRepository.issue()` in
`apps/api/src/auth/auth-token.repository.ts`); the raw token is shown exactly once and never
persisted server-side.

### 7.2 No secrets in logs or errors (FR-008, Gate G4)

Neither the connector nor any adjacent component (log aggregator, error tracker, settings UI)
MUST emit the raw token, any intermediate credential, or any sensitive ERPNext internal.
Rejection reasons MUST use the closed `RejectionReason.category` taxonomy only.

DP2's redaction discipline is authoritative:
`.specify/memory/redaction-matrix.md` (Data-Pulse-2 repo).

### 7.3 Correlation — DP2 server-side `request_id` (FR-009)

There is no dedicated correlation field or header on the wire. The end-to-end correlation
mechanism in DP2 is OTel trace-id plus the `request_id` surfaced in error responses:

> `Error.request_id` — server-side correlation id; the actual cause is recorded server-side.
> (`posting-feed.yaml`, schema `Error`)

`getCorrelationId(fallback)` in
`packages/shared/src/observability/correlation.ts` resolves the correlation id for a log
line: OTel trace-id when a valid span is active, otherwise the caller-supplied `fallback`
(typically the HTTP `request_id`).

**Connector obligation**: every pull and ack log line MUST carry the DP2 server-side
`request_id` so a log line can be traced to the originating DP2 request. The connector MUST
NOT invent a separate wire correlation field — there is none (research Decision 3).

---

## 8. Revoked-Token Operator Behavior (T010)

When the connector's `connectorBearer` token is revoked by DP2 (mid-session or otherwise),
subsequent pull and ack calls receive a generic, **non-disclosing** 401 refusal
(`posting-feed.yaml`, response `Unauthorized`):

> _"The body does not distinguish a missing / invalid / revoked connector bearer token from a
> missing tenant binding or an in-scope-but-not-permitted principal. Non-disclosing."_

The connector MUST:

1. Surface a clear operator-facing **re-authenticate** state when calls are refused with 401.
2. MUST NOT expose the raw token value, the previous token value, or any credential in the
   error message or UI shown to the operator.
3. MUST NOT continue retrying as if the failure were transient — a 401 on a well-formed
   request is a credential problem, not a server transient failure.

The operator state transitions are:

```
authenticated → token_revoked (401 received on pull or ack)
token_revoked → authenticated (operator re-provisions a fresh token)
```

No automatic token rotation is in scope for this feature; token renewal requires explicit
operator action.

---

## Summary of Connector Obligations

| Obligation | Requirement | Source |
|------------|-------------|--------|
| Auth direction | Connector authenticates TO DP2 (pull + ack) | FR-001, FR-003; `posting-feed.yaml` |
| Scope source | Derived from principal, never from body | FR-002; `tenant-context.guard.ts` `resolveToken` |
| Token security | Raw token never in logs, errors, or UI | FR-007, FR-008; Gate G4 |
| Ack idempotency | `Idempotency-Key` required on every ack | FR-005; `posting-feed.yaml` `connectorAckOutcome` |
| Dedup | Client-side: no duplicate ERPNext doc on re-pull | FR-006; `PostingWorkItem.sourceSystem + externalId` |
| Outcome taxonomy | Closed enum (`posted`/`failed_transient`/`permanently_rejected`) | FR-004; `OutcomeAckRequest` |
| Rejection categories | Closed enum, no sensitive internals in message | FR-008; `RejectionReason` |
| Retry | Bounded backoff for transient; no blind retry of permanent | FR-010 |
| ERPNext ref | `{doctype, name}` only — no field-level names | FR-004; Principle II; `ErpnextDocumentRef` |
| Correlation | Log DP2 `request_id`; invent no wire field | FR-009; `correlation.ts` `getCorrelationId` |
| Revoked token | Non-disclosing refusal; surface re-auth state | spec edge case; `posting-feed.yaml` `Unauthorized` |

---

## Open Dependency

**DP2 connector token scope** — the existing `AuthTokenScope` union (`"dashboard_api" | "pos"`)
contains no connector/machine-principal scope. Staging authentication (SC-001) is blocked
until DP2 provisions this scope. See:
[`docs/decisions/connector-token-scope.md`](./connector-token-scope.md)
