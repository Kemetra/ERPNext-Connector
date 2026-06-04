---
description: "Task list for the Data-Pulse Auth & API Policy"
---

# Tasks: Data-Pulse Auth & API Policy

**Input**: Design documents from `/specs/003-data-pulse-auth-and-api-policy/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: None. This is a documentation + policy artifact (FR-011); the spec requests no
automated tests. Verification is reviewer review against the acceptance scenarios
(quickstart.md verification table). Staging authentication is deferred (no local bench; DP2
token-scope dependency).

**Organization**: Tasks grouped by user story — US1 (authenticate + pull), US2 (idempotent
ack), US3 (secure token storage + correlation logging). The policy is ONE document; the
US1/US2/US3 sections all edit it, so those tasks are sequential (not `[P]`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3
- All paths are relative to the repository root

## Path Conventions

Documentation artifact. Policy at `docs/decisions/data-pulse-auth-and-api-policy.md`;
dependency decision at `docs/decisions/connector-token-scope.md`. Per plan.md. No code.

---

## Phase 1: Setup

**Purpose**: Create the policy document location and skeleton.

- [ ] T001 Ensure `docs/decisions/` exists (created in spec 002); create the skeleton `docs/decisions/data-pulse-auth-and-api-policy.md` with title, status, purpose, and section headers: Direction, Authentication, Idempotency & dedup, Error taxonomy, Secrets & correlation, Sources & precedence
- [ ] T002 In the skeleton, add the "Sources & precedence" section stating Data-Pulse-2 is authoritative (cite, don't redefine — FR-012, Principle I), code/contracts over prose, and that the connector authenticates TO DP2 (HTTP client; cite research.md Decision 1)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Capture the DP2 connector-token-scope dependency before the auth policy relies on it.

**⚠️ CRITICAL**: The auth section (US1) references a connector token scope that does not yet exist in DP2 — record it as a gated dependency first.

- [ ] T003 Write `docs/decisions/connector-token-scope.md`: question (which DP2 token scope authenticates the connector machine principal, given DP2 has only `dashboard_api`/`pos` today), options, recommendation, **Sign-off** line (open), `Blocks: SC-001 (staging authentication)` (research.md Decision 3 gap #2)

**Checkpoint**: The token-scope dependency is recorded; the auth policy can reference it honestly.

---

## Phase 3: User Story 1 - Authenticate to DP2 and pull securely (Priority: P1) 🎯 MVP

**Goal**: The policy documents the connector→DP2 authentication and secure pull: machine principal, opaque revocable token, scope-from-principal.

**Independent Test**: A reviewer can state the auth direction, principal type, token type, and how tenant/store scope is derived, from the Authentication section alone.

- [ ] T004 [US1] Write the **Direction** section in `docs/decisions/data-pulse-auth-and-api-policy.md`: the connector is the HTTP client (pull/ack); DP2 makes no inbound calls; cite the pull/ack endpoints in `posting-feed.yaml` (FR-003)
- [ ] T005 [US1] Write the **Authentication** section: tenant-scoped machine principal, opaque revocable bearer token (`connectorBearer`), scope derived from the principal not the body (FR-001, FR-002); cite the DP2 token machinery (`packages/auth/src/tokens.ts`, `auth-token.repository.ts`, `tenant-context.guard.ts`) and link the token-scope dependency (T003)

**Checkpoint**: Auth direction + model documented (MVP — the secure-channel definition stands on its own).

---

## Phase 4: User Story 2 - Idempotent ack & no duplicate posting (Priority: P2)

**Goal**: The policy documents idempotent outcome ack and client-side no-duplicate-posting.

**Independent Test**: A reviewer can state the idempotency key, the dedup identity, the outcome taxonomy, and the retry policy, from the Idempotency + Error sections.

- [ ] T006 [US2] Write the **Idempotency & dedup** section: required idempotency key on ack (replay vs 409 conflict); wire dedup `sourceSystem + externalId`; client-side idempotency so a re-pulled work item does not create a duplicate ERPNext document (FR-005, FR-006, Principle IV); cite `posting-feed.yaml` + O-3
- [ ] T007 [US2] Write the **Error taxonomy** section: outcome enum (`posted`/`failed_transient`/`permanently_rejected`), rejection categories (`validation`/`closed_period`/`unmapped_item`/`unmapped_account`/`other`), and client-side bounded-backoff retry for transient / no blind retry for permanent (FR-010); cite `posting-feed.yaml`
- [ ] T008 [US2] Add the **posted-outcome** rule: ERPNext document reference returned generically as `{doctype, name}` (FR-004, Principle II); cite `ErpnextDocumentRef`

**Checkpoint**: Replay-safety + taxonomy documented; US1 + US2 both stand independently.

---

## Phase 5: User Story 3 - Secure token storage & correlation logging (Priority: P3)

**Goal**: The policy documents the gate-G4 secrets discipline and correlation logging.

**Independent Test**: A reviewer can state the token-never-in-logs/UI rule and the correlation-id rule, from the Secrets & correlation section.

- [ ] T009 [US3] Write the **Secrets & correlation** section: token stored securely, never retrievable in plaintext from logs/errors/UI (FR-007, FR-008, gate G4); the connector logs the DP2 server-side `request_id` for correlation, and invents no wire correlation field (FR-009, research.md Decision 3 gap #1); cite DP2 redaction discipline + `correlation.ts`
- [ ] T010 [US3] Add the **revoked-token** operator behavior: refused calls are non-disclosing; the connector surfaces a clear re-authenticate state without exposing the token (edge case)

**Checkpoint**: G4 secrets gate + correlation documented; all three stories complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, citation verification, reviewer-readiness.

- [ ] T011 Verify every DP2 citation in the policy resolves in the Data-Pulse-2 repo (`C:\Users\user\Documents\GitHub\Data-Pulse-2`) and confirms the claim; fix any that does not resolve (FR-012, SC-005)
- [ ] T012 [P] Update `README.md` "Current Status" to note spec 003 auth policy is drafted and point to `docs/decisions/data-pulse-auth-and-api-policy.md`; mention specs 004+ are gated on it (G4)
- [ ] T013 Run the quickstart verification checklist end-to-end against the finished policy (direction, auth, idempotency, taxonomy, secrets, correlation, citations locate, token-scope dependency recorded) and confirm SC-002..SC-006 pass; SC-001 marked deferred (staging + DP2 token scope)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — the token-scope dependency (T003) must be
  recorded before the auth section (US1) references it.
- **US1 (Phase 3)**: Depends on Foundational — writes Direction + Authentication.
- **US2 (Phase 4)**: Depends on US1 (same policy doc; auth must be defined before idempotency
  on that channel).
- **US3 (Phase 5)**: Depends on US1 (token must be defined before its storage rules).
- **Polish (Phase 6)**: Depends on US1–US3.

### Within / Across Stories

- T004–T010 all edit the same policy file → author sequentially (no `[P]`).
- T003 (decision record) and T012 (README) are separate files → can be `[P]` relative to the
  policy edits, but T003 is foundational so it lands first.

### Parallel Opportunities

- T012 (README) is independent of the policy edits.
- The US1/US2/US3 sections are NOT parallel (one shared policy file).
- T003 decision record is a separate file from the policy.

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (token-scope dependency) → Phase 3 (US1 auth).
2. **STOP and VALIDATE**: the secure-channel definition (direction + auth) stands on its own.
3. This is the MVP — the auth contract is reviewable.

### Incremental Delivery

1. Setup + Foundational → skeleton + token-scope dependency recorded.
2. US1 → direction + authentication → MVP.
3. US2 → idempotent ack + taxonomy.
4. US3 → secrets gate (G4) + correlation.
5. Polish → citation verification + README + end-to-end quickstart.

---

## Notes

- [P] = different files, no dependencies.
- This feature produces NO code (FR-011) — only the policy document and one decision record.
- Constitutional anchors: FR-003/FR-012 (cite DP2, Principle I) via T002/T004/T011; FR-004
  (generic addressing, Principle II) via T008; FR-005/006 (idempotent, Principle IV) via T006;
  FR-007/008/009 (secrets + correlation, Principle V / gate G4) via T009.
- SC-001 (staging auth) is deferred — needs a staging env AND DP2 to provision the connector
  token scope (T003 dependency).
- Commit after each phase or logical group.
