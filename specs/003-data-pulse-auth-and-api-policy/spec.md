# Feature Specification: Data-Pulse Auth & API Policy

**Feature Branch**: `003-data-pulse-auth-and-api-policy`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "003 Data-Pulse Auth and API Policy — secure integration contract between Data-Pulse-2 and the connector: service auth, token storage, request/response envelope, error taxonomy, idempotency, correlation IDs, rate-limit/retry. Authoritative reference: DP2 posting-feed.yaml. Honor constitution Principles I, IV, V and security gate G4."

## Clarifications

### Session 2026-06-04

- Q: Which side authenticates to which? → A: **The connector authenticates TO Data-Pulse-2.**
  The only authoritative contract (DP2 `posting-feed.yaml`) makes the connector the HTTP
  client: it pulls work items from DP2 and acks outcomes to DP2, presenting `connectorBearer`.
  DP2 makes no outbound calls. The README arrow "DP2 → connector → ERPNext" describes
  *authority/data-origin* direction (operational traffic originates in DP2), not HTTP
  direction. The brief's "Data-Pulse can authenticate to the connector" conflates the two
  layers; the authoritative pull/ack contract governs. (See Assumptions.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authenticate to Data-Pulse-2 and pull work securely (Priority: P1)

The connector, acting as a tenant-scoped machine principal, authenticates to Data-Pulse-2
with its service bearer token and pulls the posting work feed — so operational work reaches
ERPNext only through the Data-Pulse-2 boundary (constitution Principle I).

**Why this priority**: This is the secure channel every later spec (004 product export, 005
inventory, 006 sales posting) rides on. Until the connector can authenticate to DP2 and pull
the feed, no business data can flow. It is the minimum viable secure link.

**Independent Test**: In staging, the connector presents its bearer token to DP2's pull
endpoint and receives a page of work items scoped to its tenant; an invalid/revoked token is
refused with a non-disclosing error.

**Acceptance Scenarios**:

1. **Given** a valid connector service token, **When** the connector calls the DP2 pull
   endpoint, **Then** it receives a page of work items scoped to its tenant (no other
   tenant's data appears).
2. **Given** a revoked or invalid token, **When** the connector calls DP2, **Then** the
   request is refused with a non-disclosing unauthorized response and no work is returned.
3. **Given** a successful pull, **When** the connector inspects the scope, **Then** tenant
   and store are derived from the authenticated principal, never from any request field.

---

### User Story 2 - Acknowledge outcomes idempotently (Priority: P2)

After attempting to post a work item to ERPNext, the connector reports the outcome back to
Data-Pulse-2 (posted / transient failure / permanently rejected) with an idempotency key, so
retries never double-record an outcome and DP2 has an accurate posting status.

**Why this priority**: The pull (US1) gets work in; the ack closes the loop and is what makes
the whole exchange replay-safe (Principle IV). Without idempotent ack, a retry could
duplicate-post or corrupt DP2's view. Depends on US1's authenticated channel.

**Independent Test**: In staging, the connector acks an outcome with an idempotency key;
re-sending the same outcome with the same key returns the same result (idempotent replay);
a conflicting outcome on the same key is refused.

**Acceptance Scenarios**:

1. **Given** a work item the connector has acted on, **When** it acks the outcome with an
   idempotency key, **Then** DP2 records the outcome and (for a posted outcome) the connector
   supplies the ERPNext document reference.
2. **Given** an already-sent ack, **When** the connector re-sends the same outcome with the
   same idempotency key, **Then** the response is an idempotent replay (no second recording).
3. **Given** a transient failure, **When** the connector reports it, **Then** DP2 re-offers
   the work item on a later pull, and the connector's client-side retry respects a bounded
   backoff.

---

### User Story 3 - Store the token and surface failures without leaking secrets (Priority: P3)

An operator configures the connector's Data-Pulse-2 service token, and the connector stores
it securely and logs its activity with a correlation identifier — such that the token never
appears in logs or the UI, and failures are diagnosable (constitution Principle V, gate G4).

**Why this priority**: The channel (US1/US2) must be operable and auditable without exposing
credentials. This hardens the secure link rather than enabling it, so it is P3 — but it is
the explicit security gate (G4) for this spec.

**Independent Test**: An operator sets the token; it is stored such that the raw value is not
retrievable in plaintext from logs or the UI; connector log lines for a pull/ack carry a
correlation identifier that ties them to the DP2 server-side request.

**Acceptance Scenarios**:

1. **Given** a configured service token, **When** an operator or developer inspects logs,
   error messages, or the settings UI, **Then** the raw token value never appears.
2. **Given** a connector pull or ack, **When** it is logged, **Then** the log line carries a
   correlation identifier (the DP2 server-side request identifier) enabling end-to-end trace.
3. **Given** a rejected work item, **When** the rejection is recorded, **Then** the reason
   uses the defined category taxonomy and carries no credentials or sensitive ERPNext
   internals.

### Edge Cases

- What happens when the connector's token is revoked mid-session? Subsequent calls MUST be
  refused with a non-disclosing unauthorized response; the connector MUST surface a clear
  operator-facing "re-authenticate" state without exposing the token.
- What happens when a pull cursor is stale/unservable? The contract returns a re-baseline
  directive (a conflict outcome); the connector MUST honor it and re-pull from the directed
  point, not silently drop work.
- What happens when the same work item is pulled twice (at-least-once delivery)? The connector
  MUST NOT create a duplicate ERPNext document — client-side idempotency keyed on the work
  item's stable dedup identity (Principle IV).
- What happens when Data-Pulse-2 has no dedicated machine-principal token scope provisioned
  yet? This is recorded as a dependency on DP2 (see Assumptions / Dependencies), not assumed
  resolved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The connector MUST authenticate to Data-Pulse-2 as a tenant-scoped, revocable
  **machine principal**, presenting an opaque service bearer token, per the DP2 connector
  contract. *(Constitution Principle I)*
- **FR-002**: Tenant and store scope MUST be derived from the authenticated principal, never
  accepted from any request field (no body-supplied tenant/store/actor).
- **FR-003**: The connector MUST pull work items from Data-Pulse-2 (it is the HTTP client);
  Data-Pulse-2 makes no inbound calls to the connector. No path bypasses Data-Pulse-2.
  *(Principle I)*
- **FR-004**: The connector MUST acknowledge each work item's outcome to Data-Pulse-2 using
  the defined outcome taxonomy (posted / transient failure / permanently rejected), supplying
  the ERPNext document reference on a posted outcome, addressed generically as
  `{doctype, name}`. *(Principle II)*
- **FR-005**: Outcome acknowledgement MUST be idempotent — re-sending the same outcome with
  the same idempotency key MUST NOT record a second outcome; a conflicting outcome on a reused
  key MUST be refused. *(Principle IV)*
- **FR-006**: The connector MUST NOT create a duplicate ERPNext document when the same work
  item is delivered more than once, using the work item's stable dedup identity
  (source-system + external-id). *(Principle IV)*
- **FR-007**: The connector MUST store its Data-Pulse-2 service token securely such that the
  raw token value is never retrievable in plaintext from logs, error messages, or the UI.
  *(Gate G4)*
- **FR-008**: The connector MUST NOT log, display, or include in error messages any
  credential, token, or sensitive ERPNext internal. Rejection reasons MUST use the defined
  category taxonomy only. *(Principle V, Gate G4)*
- **FR-009**: The connector MUST record a correlation identifier (the Data-Pulse-2
  server-side request identifier) on its pull/ack log lines to enable end-to-end tracing.
  *(Principle V)*
- **FR-010**: The connector's client-side retry of transient failures MUST use a bounded
  backoff and MUST rely on idempotency so re-posting is safe; permanently-rejected items MUST
  NOT be retried blindly.
- **FR-011**: This feature is a **policy/contract-alignment document**; it MUST NOT implement
  connector endpoints or token-handling code. The auth model MUST be documented and the
  contract cited before any business endpoint is implemented (specs 004+). *(Principle VII)*
- **FR-012**: The policy MUST cite the authoritative Data-Pulse-2 contract and auth model
  (its connector posting contract and token machinery), not redefine them. *(Principle I)*

### Key Entities *(include if feature involves data)*

- **Connector Service Principal**: The tenant-scoped machine identity the connector uses to
  authenticate to Data-Pulse-2; carries a revocable opaque bearer token. Owned by
  Data-Pulse-2's auth model; cited, not redefined.
- **Service Token (connector-side)**: The secret the connector stores to authenticate. The
  connector-side concern is secure storage + non-exposure (FR-007/008); the token's issuance,
  hashing, and revocation are owned by Data-Pulse-2.
- **Posting Work Item / Outcome**: The unit pulled from DP2 and acked back, with its dedup
  identity and outcome taxonomy. Shape owned by the DP2 contract; cited.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In staging, the connector authenticates to Data-Pulse-2 and pulls a tenant-
  scoped work feed on the first attempt with a valid token; 100% of invalid/revoked-token
  attempts are refused.
- **SC-002**: 100% of repeated outcome acks with the same idempotency key result in a single
  recorded outcome (no double-recording).
- **SC-003**: 0 occurrences of a raw token or credential appearing in logs, error messages,
  or the UI across an install→authenticate→pull→ack→uninstall cycle.
- **SC-004**: 100% of connector pull/ack log lines carry a correlation identifier that ties
  them to the Data-Pulse-2 server-side request.
- **SC-005**: A developer can, from this policy alone, state the auth direction, token-storage
  rule, idempotency key, outcome taxonomy, and retry policy without reading DP2 source.
- **SC-006**: No connector business endpoint is implemented until this policy is reviewed
  and the auth model documented (Principle VII gate).

## Assumptions

- **Auth direction (authoritative).** The connector authenticates **to** Data-Pulse-2 and is
  the HTTP client (pull/ack), per the DP2 `posting-feed.yaml` contract; DP2 makes no outbound
  calls. The README phrasing "Data-Pulse can authenticate to the connector" describes
  authority/data-origin direction, not HTTP direction. If a connector-exposed inbound surface
  is genuinely intended, that is a different feature and would need its own DP2-side contract.
- **Data-Pulse-2 is authoritative** for the auth model, token issuance/hashing/revocation,
  the request/response envelope, the dedup key, the idempotency-key mechanism, the outcome and
  rejection-category taxonomies, and pagination/retry semantics. This policy cites them.
- **Correlation is via the DP2 server-side request identifier** (and the platform's trace
  identifier) surfaced on errors — there is **no** dedicated correlation field on the wire.
  The connector logs the request identifier; it does not invent a correlation field.
- **Token security model**: DP2 stores only a hash of the token (not the raw value) and the
  token is opaque-random and revocable. The connector's obligation is to store its copy of the
  raw token securely and never expose it (FR-007/008). (The connector's at-rest storage
  mechanism is a plan-phase decision.)
- This is a documentation/policy artifact (no code), consistent with the exit criterion
  "auth model is documented before business endpoints are implemented" and Principle VII.

## Dependencies

- **DP2 connector token scope** — Data-Pulse-2's current token scopes are operational
  (`dashboard_api`, `pos`); a **dedicated connector/machine-principal scope does not yet
  exist** in DP2. Provisioning that scope (and issuing the connector its token) is a
  Data-Pulse-2-side dependency this policy depends on. Recorded here as a known gap, not an
  assumed fact; it does not block writing the policy but blocks staging authentication
  (SC-001) until DP2 provides it.
