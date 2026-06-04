# Phase 0 Research: Data-Pulse Auth & API Policy

**Feature**: 003-data-pulse-auth-and-api-policy | **Date**: 2026-06-04

Source: a read-only survey of Data-Pulse-2 (`C:\Users\user\Documents\GitHub\Data-Pulse-2`),
focused on the connector↔DP2 boundary. Every citation below was verified against the real
repo. **Code/contracts outrank prose** (the authoritative contract resolved the auth-direction
contradiction in the brief). No open `NEEDS CLARIFICATION` items remain.

---

## Decision 1: Auth direction — connector authenticates TO Data-Pulse-2

**Decision**: The connector is the HTTP **client**. It pulls work from DP2 and acks outcomes
to DP2, presenting `connectorBearer`. DP2 makes **no** outbound calls to the connector.

**Rationale**: The only authoritative contract — DP2 `posting-feed.yaml` — defines exactly
two connector-facing operations, both with the connector as caller:
`GET /api/connector/v1/erpnext/postings` (`connectorPullPostings`) and
`POST /api/connector/v1/erpnext/postings/{workItemRef}/outcome` (`connectorAckOutcome`).
Both surveys of DP2 confirm "DP2 makes no outbound calls; the connector pulls/acks." The
README arrow "DP2 → connector → ERPNext" is *authority/data-origin* direction, not HTTP
direction. Writing a connector-as-server spec would re-derive a contract DP2 does not have
(Principle I violation). Confirmed with the user.

**Alternatives considered**: Connector-exposed inbound surface that DP2 calls — rejected; no
DP2-side outbound client or contract exists; would be a different feature.

**Authoritative source**: `packages/contracts/openapi/erpnext-connector/posting-feed.yaml`;
`specs/012-erpnext-connector-contracts/connector-lifecycle.md` (§1 credential ownership, §2
connector-to-DP2 auth).

---

## Decision 2: Authoritative DP2 citations for the policy (cite, don't redefine)

| Policy element | DP2 authoritative source |
|----------------|--------------------------|
| Security scheme `connectorBearer` (http bearer; opaque, revocable, tenant-scoped machine principal) | `posting-feed.yaml` security scheme `connectorBearer`; `packages/contracts/openapi/auth.openapi.yaml` `bearerAuth` baseline |
| Pull endpoint | `posting-feed.yaml` `GET /api/connector/v1/erpnext/postings` (`connectorPullPostings`) |
| Ack endpoint (idempotency required) | `posting-feed.yaml` `POST .../{workItemRef}/outcome` (`connectorAckOutcome`, `x-idempotency: required`) |
| Envelope shapes | `posting-feed.yaml` `PostingWorkItem`, `Sale`, `SaleLine`, `OutcomeAckRequest`, `ErpnextDocumentRef`, `RejectionReason`, `PostingFeedPage` |
| Wire dedup key | `sourceSystem + externalId` (O-3); `posting-feed.yaml` PostingWorkItem; `specs/012-.../contract-obligations.md` O-3 |
| Ack idempotency mechanism | required `Idempotency-Key` header, tuple `(method, route, clientId, key)`; same-outcome replay → idempotent 200; conflict → 409 `idempotency_key_conflict` |
| Outcome taxonomy | `posted | failed_transient | permanently_rejected` (`OutcomeAckRequest.outcome`) |
| Rejection categories | `validation | closed_period | unmapped_item | unmapped_account | other` (`RejectionReason.category`) |
| Pagination | cursor-based: `since` (opaque cursor) + `limit` (1–500, default 100); stale cursor → 409 `snapshot_required` (re-baseline) |
| Retry/DLQ ownership | `failed_transient` → DP2 re-offers (bounded retry budget); `permanently_rejected` → DP2 dead-letters; at-least-once delivery |
| Token machinery | `packages/auth/src/tokens.ts` (opaque random + SHA-256 hash; constant-time compare), `apps/api/src/auth/auth-token.repository.ts` (issue/revoke; raw never persisted), `packages/auth/src/types.ts` (`RawToken`/`TokenHash` branded types) |
| Tenant/scope from principal not body | `apps/api/src/context/tenant-context.guard.ts` `resolveToken`; `OutcomeAckRequest` `additionalProperties: false` rejects body-supplied scope |
| Correlation / secrets discipline | `packages/shared/src/observability/correlation.ts` (OTel trace-id + `request_id`); `Error.request_id` in `posting-feed.yaml`; `.specify/memory/redaction-matrix.md` (DP2) |

**Rationale**: DP2 owns all of this; the policy cites it (Principle I). The connector-side
delta the policy *owns* is: secure storage of its copy of the token, client-side retry/backoff
against `failed_transient`, client-side idempotency so re-pull doesn't double-post to ERPNext,
and logging the DP2 `request_id` for correlation.

---

## Decision 3: Three DP2 gaps — recorded, not assumed

The survey flagged three facts that, if assumed from memory, would produce a wrong policy:

1. **No `correlationId` on the wire.** DP2 has no correlation field/header anywhere; the
   end-to-end mechanism is OTel trace-id + the `request_id` surfaced on errors
   (`Error.request_id`). **Policy stance**: the connector logs the DP2 `request_id`; it
   invents no correlation field (FR-009).
2. **No dedicated connector/machine token scope in DP2 yet.** Existing scopes are
   `dashboard_api` and `pos` (`packages/auth/src/types.ts`, `auth.guard.ts`). A connector
   machine-principal scope does not exist. **Policy stance**: recorded as a DP2-side
   **dependency** (decision record `docs/decisions/connector-token-scope.md`) that blocks
   staging authentication (SC-001) until DP2 provisions it — NOT assumed resolved.
3. **Tokens are opaque-random + SHA-256, not argon2id** (argon2id is passwords-only in DP2).
   **Policy stance**: the Assumptions/policy state the hash model correctly.

---

## Open items

None. All Technical Context is resolved; no `NEEDS CLARIFICATION` remains. The DP2
connector-token-scope gap is a tracked external dependency, not an unresolved unknown.
