# Draft D9+D10 — Connector Admin Counterpart: Registration-Linked, Rotatable Service Bearer

> **DRAFT — NOT DISPATCHED.** Planning artifact under docs-only Orchestrator. No implementation, no contract, no migration, no gate mutation. Requires explicit scoped owner approval + G10 verification before any sibling-repo dispatch.

**Status:** SPECIFY-ONLY / DRAFT — for owner review. **Date:** 2026-06-11. **Owning repo:** Retail-Tower-ERP-Next-Connector. **Deciders:** Owner (Ahmed Shaaban).
**Gating label:** gated — requires owner approval + G10 verification before any dispatch.

**Relation to 028:** Realizes 028 §20 (Connector follow-up: *"the still-absent 018 `connector-admin` counterpart"*) and §15 (Connector service-auth boundary; OQ-10-resolved opaque revocable `connectorBearer` as v1). 028 owns the project-wide identity/access boundary this draft conforms to; this draft does not re-specify it. Drift-map item **D9 + D10** (one combined node — drift-map: `D9→D10` REFUTED; co-gated siblings on already-shipped 018, not a chain; authoritative kernel node `CON-018-COUNTERPART`).

---

> ### authoring & placement notes (owner can redirect)
>
> - **Docs-only.** Authored under the Orchestrator's allowed `docs/**` surface, in a `drafts/` folder. No `.specify/` tooling exists in this repo, so this follows the speckit *structure* (mirroring the Connector's own `specs/003-*` house style + the Orchestrator's `028`/`029` specs) but was authored manually — no template copy, no `feature.json`, no branch.
> - **Not a dispatch, not a kernel mutation.** This feeds a future Queue Item under gate **G10**; it does not advance or mutate the kernel queue, touch `docs/gates/**`, `docs/kernel/**`, `docs/status/**`, or any sibling implementation repo.
> - **Conforms to an already-shipped boundary.** The DP-2 side (018: `connector-admin.yaml` + migration `0021_connector_registration.sql` + the tightened `ConnectorAuthGuard`, PR #516) is **shipped and CLOSED on DP-2 `origin/main`**. This draft is a *downstream Connector consumer*; it authors no DP-2 contract, migration, or guard.
> - **Key framing correction (grounded in E-2).** `connector-admin.yaml` is **human-session-only** (`cookieAuth`, rejects machine bearers). The Connector is a machine with no `dp2_session`, so the Connector is **not** the HTTP client of the admin surface. This draft specifies the Connector-side **config + credential-lifecycle model and the cutover sequencing**; a human tenant-admin operates the admin surface (Console-mediated), and the Connector **consumes** the issued registration-linked credential.

## Clarifications

### Session 2026-06-11

- Q: Is the Connector the HTTP client of the 018 admin surface (`connector-admin.yaml`)? → A: **No — the Connector consumes the issued credential; a human tenant-admin operates the admin surface** — the shipped contract is `cookieAuth`-session-only and explicitly rejects a `dashboard_api` machine bearer (E-2). The Connector is a machine with no `dp2_session`. So this item delivers the Connector-side config/lifecycle model + cutover, not a machine→admin-API client. *(Where the admin-API client itself lives — Console or operator tooling — is a cross-repo observation, OQ-3 below, not this item's deliverable.)*
- Q: Does the Connector's machine credential and posting path change? → A: **No — the 012 posting-feed surface (`connectorBearer`, scope `connector`, pull/ack) is unchanged** — D9/D10 only changes how the credential is *provisioned, linked, and rotated/revoked* (018), not the runtime auth scheme on the feed (028 §15 OQ-10-resolved: opaque revocable bearer stays the v1 target; mTLS is the documented upgrade path).
- Q: Does this draft introduce a Postgres/SQL migration? → A: **No — the only SQL migration in the chain is DP-2's upstream-shipped `0021` (E-3); it is a dependency, not a deliverable** — the Connector-side schema delta is a **Frappe DocType change** to `Connector Settings` (additive lifecycle fields), applied by `bench migrate`, not hand-written SQL.
- Q: Credential-only swap, or record the registration/credential lifecycle on the Connector side? → A: **Record the lifecycle (registration ref + credential ref + `expires_at`)** — the D9 target is "lifecycle no longer purely reactive"; storing the credential's bounded `expires_at` (server default 90 days, E-1) lets the Connector warn *before* expiry instead of only catching a 401 after the fact. This makes it a Frappe schema delta → G3-tagged (DocType change, not SQL).
- Q: Is the legacy hand-edited `dp2_token` cut over gracefully, or does it break? → A: **It breaks the moment the tightened US4 guard reaches the Connector's environment (E-4) — cutover MUST complete before that** — the US4 `ConnectorAuthGuard` enforces the registration-link **at runtime, independently of the DB consistency CHECK that 0021 deferred** (E-3/E-4). An unlinked token gets a non-disclosing 401 as soon as that guard deploys. So the cutover (register → issue linked credential → reconfigure → verify → revoke legacy) must finish *before* US4 enforcement is live in the Connector's env.
- Q: Auth scheme for the connector↔DP-2 feed — keep opaque bearer or upgrade? → A: **Keep the shipped opaque revocable `connectorBearer` for v1; mTLS is the documented upgrade path** — directly inherits 028 §15 / OQ-10 (resolved 2026-06-11). Not re-litigated here.

## Evidence basis (verified this session, `origin/main`, 2026-06-11)

| Repo | `origin/main` HEAD | What was read |
|---|---|---|
| Data-Pulse-2 | `6588e86` (badge) / `0c57fed` (substantive #544) | `packages/contracts/openapi/connector/connector-admin.yaml`; `packages/db/drizzle/0021_connector_registration.sql`; `apps/api/src/auth/connector-auth.guard.ts` |
| Retail-Tower-ERP-Next-Connector | `bc768ad` (#27) | `…/doctype/connector_settings/connector_settings.json` (+`.py`); `…/posting/transport.py`; `docs/decisions/connector-token-scope.md`; `docs/decisions/data-pulse-auth-and-api-policy.md` |
| Retail-Tower-Orchestrator | `main` (this repo, clean) | 028 spec §15/§16/§19/§20; `docs/roadmap/auth-028-drift-map.md` (D9/D10 row + DAG); `docs/gates/cross-repo-gates.md` (G10/G2/G3) |

Current-runtime facts (kept distinct from *target* and *open decisions*):

- **E-1 (admin surface is SHIPPED on DP-2).** `connector-admin.yaml` (018, `version: 1.0.0-draft`) defines six operations — `tenantAdminRegisterConnectorInstance`, `tenantAdminListConnectorInstances`, `tenantAdminIssueConnectorCredential`, `tenantAdminRotateConnectorCredential` (atomic immediate-revoke, requires `Idempotency-Key`), `tenantAdminRevokeConnectorCredential`, `tenantAdminDisableConnectorInstance`. A `connector_registration` is the stable per-tenant identity that **survives credential rotation**; credentials live in `auth_tokens` (scope `connector`) linked to a registration; the raw secret is returned **exactly once** (`IssuedCredential.secret`) at issue/rotate. Optional `expires_in_days` (server default 90, capped ≤365; never unbounded).
- **E-2 (admin surface is SESSION-ONLY — the Connector cannot call it).** `connector-admin.yaml` `security: [{ cookieAuth: [] }]` (httpOnly `dp2_session`) + a privileged tenant role (owner/tenant_admin). The contract states explicitly: *"a `dashboard_api` MACHINE bearer is REJECTED even when it carries the right role … It is NOT the 012 `connectorBearer` machine scheme and NOT the POS `clerkJwt` device scheme."* The Connector (a Frappe machine principal, no human session) therefore **consumes** issued credentials but does not operate this surface.
- **E-3 (registration link shipped; consistency CHECK deferred).** `0021_connector_registration.sql` creates `connector_registration` (RLS enable+force; `UNIQUE (tenant_id, environment, erpnext_site_ref)`), adds the additive nullable FK `auth_tokens.connector_registration_id`, pins `auth_tokens.scope` to a six-member CHECK **including `connector`**, and adds `uq_auth_tokens_active_connector_credential` (at-most-one active connector credential per registration). The connector-token **consistency CHECK** `(scope='connector') = (connector_registration_id IS NOT NULL)` is **DEFERRED** — a legacy unlinked connector token may exist (owner-confirmed 2026-06-06); the link is enforced by the US4 guard at runtime instead.
- **E-4 (US4 guard enforces the link at runtime, independently of the DB CHECK).** `connector-auth.guard.ts` requires `principal.kind === "token"` AND `principal.scope === "connector"`, then calls `findActiveConnectorCredentialByTokenId(principal.tokenId)`; a `null` result (covering expired / revoked / **unlinked** / disabled-instance / cross-tenant) yields a single **non-disclosing 401**. The breaking-change intent is documented in the migration comment block — `packages/db/drizzle/0021_connector_registration.sql` (L141) and the 018 execution-map/plan/tasks: *"GUARD-TIGHTENING-IS-BREAKING-FOR-LEGACY-TOKENS"* — not in the guard source itself. So an unlinked hand-edited token breaks the instant this guard reaches the Connector's environment.
- **E-5 (Connector runtime today — reactive, unlinked).** `connector_settings.json` (Single DocType) holds `dp2_base_url` + `dp2_token` (a `Password` field — *"opaque connectorBearer token … Hand-issued DP2-side; the connector only presents it"*). No `connector_registration` reference, no credential id, no `expires_at`. Lifecycle is purely reactive: `data-pulse-auth-and-api-policy.md` §8 documents the only state machine as `authenticated → token_revoked (401) → authenticated (operator re-provisions a fresh token)` and states *"No automatic token rotation is in scope … token renewal requires explicit operator action."* `connector_settings.py` carries no business logic.
- **E-6 (the Connector's own scope decision is now satisfied by 0021).** `connector-token-scope.md` signed **Option A** (2026-06-04): *"DP2 provisions a new dedicated connector scope … MUST NOT reuse `dashboard_api`/`pos`/`pos_operator`,"* status "🟢 SIGNED — awaiting DP2 delivery," with SC-001 blocked on DP-2 delivery. DP-2's `0021` now ships the `connector` scope (E-3) and the admin issue/rotate/revoke surface (E-1) — **the awaited delivery has landed**; this draft is the Connector-side adoption of it.

## 1. Summary

Today the Connector authenticates to Data-Pulse-2 with a hand-edited opaque `dp2_token` stored in the `Connector Settings` Single DocType (E-5). That token has **no link to a `connector_registration`** and **no recorded lifecycle** (no credential id, no `expires_at`); the only lifecycle behavior is reactive — a 401 is interpreted as `token_revoked` and an operator pastes in a fresh hand-issued token.

DP-2 has since **shipped** (018, PR #516) the operator-facing counterpart: a `connector_registration` identity that survives rotation, a `connector`-scoped credential linked to it, and an admin surface to register / issue / rotate / revoke / disable (E-1/E-3). Critically, the tightened `ConnectorAuthGuard` now **requires** the presented token to be a `connector`-scoped credential linked to a non-disabled registration in its own tenant, enforced at runtime independently of the deferred DB CHECK (E-4). An unlinked legacy token will be refused with a non-disclosing 401 once that guard is live in the Connector's environment.

This draft specifies the Connector-side work to **adopt the registration-linked credential and stop being a reactive, unlinked client**, in two co-delivered halves (one node, `CON-018-COUNTERPART`):

- **D9** — model the Connector's configuration around a registration-linked, lifecycle-aware credential (replacing the bare hand-edited `dp2_token`): record the registration ref, credential ref, and bounded `expires_at`, so the operator can be warned before expiry instead of only after a 401.
- **D10** — sequence the **cutover** so the Connector is presenting a registration-linked, `connector`-scoped credential **before** the tightened US4 guard is enforced live (backfill → link/reissue → reconfigure → verify → revoke legacy), avoiding a hard 401 outage.

Because the admin surface is human-session-only (E-2), the Connector **never calls it**: a human tenant-admin (Console-mediated or session tooling) registers the instance and issues the credential; the raw secret (shown once) is configured into the Connector; the Connector then presents it on the unchanged 012 posting-feed (`connectorBearer`).

## 2. Goals

- **G-1.** Replace the bare hand-edited `dp2_token` model (E-5) with a **registration-linked, lifecycle-aware credential model** on the Connector side, conforming to the shipped 018 surface (E-1/E-3).
- **G-2.** Record enough credential lifecycle locally (registration ref + credential ref + `expires_at`) for the Connector to **warn before expiry** rather than only reacting to a 401 (closes the "purely reactive" drift).
- **G-3.** Define a **safe cutover** that lands a registration-linked `connector`-scoped credential **before** the tightened US4 guard (E-4) is enforced live, so the Connector never hits the breaking non-disclosing 401.
- **G-4.** Keep the **012 posting-feed runtime auth unchanged** — opaque `connectorBearer`, scope `connector`, pull/ack (028 §15 / OQ-10).
- **G-5.** Preserve all existing secret-handling discipline (G4 / 003): the raw secret stays a Frappe `Password` field, never logged, never surfaced in UI/errors; the raw secret is captured once at issue/rotate (E-1) and never re-retrieved.
- **G-6.** Conform to the credential-scope-non-interchangeability boundary (028 SR-10): the connector credential is a `connector`-scoped machine credential only; it authorizes no user/operator/device action.

## 3. Non-goals

- **N-1.** No code, Frappe Python, OpenAPI/YAML, SQL migration, package/lock, CI, generated-file, secret, env, or deployment change in this task. (Orchestrator is docs-only; SPECIFY-ONLY draft.)
- **N-2.** No edit to any DP-2 file. `connector-admin.yaml`, `0021_connector_registration.sql`, and `connector-auth.guard.ts` are **shipped upstream dependencies** (E-1/E-3/E-4); this draft conforms, it does not author or modify them.
- **N-3.** No Connector-side admin-API client. The admin surface is session-only (E-2); a machine→admin-API client would be rejected by the shipped contract.
- **N-4.** No change to the 012 posting-feed contract or its `connectorBearer` auth scheme (G-4).
- **N-5.** No automatic self-rotation by the Connector — the Connector cannot mint its own credential (the admin surface is session-only). Rotation is operator/admin-initiated via the 018 surface; the Connector's role is to detect impending expiry and surface it (OQ-1).
- **N-6.** No mTLS or signed-request rebuild — explicitly the documented upgrade path, not v1 (028 §15 / OQ-10).
- **N-7.** No raw secret value in any output, log, doc, fixture, or DocType default.
- **N-8.** No assertion that any DP-2 PR/migration is "done" beyond what `origin/main` evidence shows (E-1…E-4 cite the shipped files/PR #516).

## 4. Actors & surfaces

| Actor / surface | Role in this draft |
|---|---|
| **Tenant admin (human)** | Operates `connector-admin.yaml` (session-only, E-2): register instance, issue/rotate/revoke credential, disable instance. Hands the once-shown raw secret to the Connector operator. |
| **Connector operator / ops** | Configures the issued secret + registration/credential refs into `Connector Settings`; runs `bench migrate` for the DocType delta; coordinates the cutover window. |
| **Connector (Frappe app, machine principal)** | **Consumes** the registration-linked `connector`-scoped credential; presents it on the 012 posting-feed (`connectorBearer`); records its lifecycle (`expires_at`); warns before expiry. **Never calls the admin surface.** |
| **DP-2 admin API (018, shipped)** | The session-only counterpart that registers + manages the credential lifecycle (E-1). Upstream dependency. |
| **DP-2 `ConnectorAuthGuard` (US4, shipped)** | Enforces `connector`-scope + non-disabled-registration link at runtime (E-4). The thing that breaks an unlinked legacy token. |

## 5. Connector configuration model (D9 — the schema seam)

The `Connector Settings` Single DocType (E-5) is extended **additively** with credential-lifecycle fields (a Frappe DocType change applied by `bench migrate` — **not** a SQL migration; the only SQL migration in the chain is DP-2's upstream `0021`, E-3):

| Field (target) | Type | Purpose |
|---|---|---|
| `dp2_base_url` *(existing)* | Data | Unchanged. |
| `dp2_token` *(existing)* | Password (secret) | Unchanged role: the raw `connectorBearer` the Connector presents. Now sourced from the once-shown `IssuedCredential.secret` (E-1), not hand-minted. Still a `Password` field, never logged (G4). |
| `dp2_connector_registration_id` *(new)* | Data (uuid label) | The `connector_registration` id the active credential is linked to (E-3). Operator-facing, NOT a secret. Lets list/audit on the DP-2 side correlate. |
| `dp2_credential_id` *(new)* | Data (uuid label) | The `auth_tokens` credential id (`IssuedCredential.credential_id`, E-1). NOT a secret. Identifies *which* credential is configured, for rotate/revoke correlation. |
| `dp2_credential_expires_at` *(new)* | Datetime | The credential's bounded expiry (`IssuedCredential.expires_at`, E-1). Drives the pre-expiry warning (G-2). NOT a secret. |
| `dp2_credential_issued_at` *(new, optional)* | Datetime | Provenance of the current credential (audit/correlation). |

- The registration / credential ids and timestamps are **identifiers and status, never secrets** — they mirror what the DP-2 `ConnectorInstance` / `CredentialStatus` projections expose (E-1), which themselves never carry a secret or hash.
- Only `dp2_token` remains a `Password` secret field. The lifecycle fields are non-secret metadata.
- A reclassification rule (mirroring DP-2's §XIV note in `0021`): if any future field would carry a secret/PII, it re-triggers the secret-handling review (G4).

## 6. Credential lifecycle model (D9/D10 — replacing the reactive state machine)

Today's reactive state machine (E-5): `authenticated → token_revoked (401) → authenticated (operator re-provisions)`. Target — a lifecycle-aware model the Connector can act on **proactively**:

```
unregistered ──(admin registers instance, 018)──► registered (no credential)
registered ──(admin issues connector-scoped credential, 018; secret shown once)──► provisioned
provisioned ──(operator configures secret + reg/cred refs + expires_at into Settings)──► active
active ──(expires_at approaching)──► expiry_warning   [Connector surfaces; cannot self-rotate (N-5)]
active|expiry_warning ──(admin rotates, 018 atomic)──► provisioned (new secret; same registration)
active ──(admin revokes / disables instance, 018)──► revoked  [next call → US4 non-disclosing 401, E-4]
active ──(401 on pull/ack)──► auth_failed  [surface re-auth; do NOT blind-retry — inherits 003 §8]
```

- The **registration survives rotation** (E-1/E-3): a rotate swaps `dp2_token` + `dp2_credential_id` + `dp2_credential_expires_at`, but `dp2_connector_registration_id` is unchanged.
- **Pre-expiry warning (G-2)** is the substantive new behavior vs E-5: the Connector compares `now()` to `dp2_credential_expires_at` and surfaces an operator-facing "credential expiring — request rotation" state *before* a 401. The Connector **cannot** self-rotate (admin surface is session-only, N-5); it can only warn + prompt the operator/admin.
- The **401 handling is unchanged from 003 §8**: non-disclosing refusal → surface re-authenticate state, never expose the raw/previous token, never blind-retry a 401 as transient.

## 7. Cutover sequencing (D10 — the breaking-change-avoidance order)

The US4 guard enforces the link **at runtime, independently of the deferred DB CHECK** (E-3/E-4). The hand-edited unlinked legacy token (E-5) is therefore live only until US4 enforcement reaches the Connector's environment. The cutover MUST complete before that:

1. **Backfill / register** — a human tenant-admin registers the Connector instance (`tenantAdminRegisterConnectorInstance`, E-1) for the correct `(environment, erpnext_site_ref)` — at most one active per tuple (E-3 unique constraint).
2. **Issue a linked credential** — admin issues a `connector`-scoped credential for that registration (`tenantAdminIssueConnectorCredential`, E-1); raw secret shown **once**, with a bounded `expires_at`.
3. **Reconfigure the Connector** — operator runs the DocType `bench migrate` (§5), then configures `dp2_token` (the new secret) + `dp2_connector_registration_id` + `dp2_credential_id` + `dp2_credential_expires_at`.
4. **Verify** — confirm the Connector can `connectorPullPostings` + `connectorAckOutcome` (012 feed, unchanged) under the new linked credential — i.e. it passes the tightened US4 guard (`findActiveConnectorCredentialByTokenId` returns the linked instance, E-4).
5. **Revoke the legacy token** — admin revokes the old hand-edited credential (`tenantAdminRevokeConnectorCredential`, E-1) only **after** step 4 verifies the new one works (no lockout window).

This whole sequence is **rollout-coordinated**: it must finish before US4 enforcement is live in the Connector's environment, or the legacy token gets the breaking non-disclosing 401 (E-4). *(This brushes rollout gates G8/G9, but per the brief this item's gate tags stay G10/G2/G3.)*

## 8. Security & conformance

- **S-1.** The raw secret is captured once (`IssuedCredential.secret`, E-1), stored only in the `dp2_token` `Password` field, never logged, never in UI/errors (G4 / 003 §7; G-5).
- **S-2.** Lifecycle fields (`registration_id`, `credential_id`, `expires_at`) are non-secret identifiers/status only (§5); they mirror what DP-2's non-secret `ConnectorInstance`/`CredentialStatus` projections expose.
- **S-3.** Scope non-interchangeability (028 SR-10): the credential is `connector`-scoped only; it authorizes no user/operator/device action; the Connector rejects POS-originated calls (028 §15 CM-5, unchanged).
- **S-4.** Least privilege + revocability (028 §6 connector row; G4 / SR-11/SR-12): the credential is bounded (`expires_at`), DP-2-revocable, and atomically rotatable (E-1) — the v1 rotation path the Connector previously lacked.
- **S-5.** Opaque-bearer-as-v1 (028 §15 / OQ-10): the scheme stays opaque revocable `connectorBearer`; mTLS is the documented upgrade path, not built here (N-6).

## Acceptance criteria

- **A-1.** The Connector config model carries a `connector_registration` reference + credential reference + bounded `expires_at` (not just a bare token) — §5.
- **A-2.** The Connector can warn on impending credential expiry from recorded lifecycle state, instead of only reacting to a 401 — §6, G-2.
- **A-3.** A documented cutover sequences register → issue-linked → reconfigure → verify → revoke-legacy, completing before US4 enforcement is live — §7, grounded in E-4.
- **A-4.** The 012 posting-feed runtime auth (`connectorBearer`, scope `connector`, pull/ack) is unchanged — §1, G-4, N-4.
- **A-5.** The Connector never calls the session-only admin surface; a human tenant-admin operates it and the Connector consumes the issued credential — §4, E-2, N-3.
- **A-6.** No DP-2 file is authored or modified; the shipped 018 surface (E-1/E-3/E-4) is conformed to, cited by PR #516 / file path — N-2.
- **A-7.** Raw secret handling discipline is preserved (Password field, never logged, captured once) — §8 S-1, G-5.
- **A-8.** No implementation, contract, migration, or gate mutation performed in this draft — N-1.

## Dependencies & sequencing

**Gate dependencies (must hold before any dispatch):**
- **G10 — Identity & Access Boundary Gate (consumed; MUST be verified).** This is an auth/identity/access-touching item; per `cross-repo-gates.md` it MUST list G10 and the boundary decisions (028 §22) MUST be signed. Label: *gated — owner approval + G10 verification before dispatch.*
- **G2 — Contract Gate (consumed; already SATISFIED).** The connector↔DP-2 contracts this conforms to are shipped: `connector-admin.yaml` (018, PR #516) and `posting-feed.yaml` (012). This draft authors **no** OpenAPI — it conforms. Evidence: E-1 (admin contract) + 003 policy (posting-feed). 
- **G3 — Migration Gate (consumed for the DocType delta only).** The Connector-side change is a **Frappe `Connector Settings` DocType delta** (`bench migrate`), not a SQL migration; G3's review/idempotency/rollback discipline applies to that delta. The only SQL migration in the chain (`0021`) is **DP-2-owned and upstream-shipped** (E-3) — a dependency, not a deliverable.

**DAG dependencies (drift-map verified):**
- `CON-018-COUNTERPART` (this combined D9+D10 node) **`depends_on: [DP-018-IMPL]`** — gated **only** on DP-2's already-shipped+CLOSED 018 (PR #516 / migration `0021` + `connector-admin.yaml`).
- **`D9→D10` is REFUTED as a chain** — D9 and D10 are **co-gated siblings on shipped 018, not a sequence**; the kernel models them as **one node** with no internal ordering edge. (The `backfill → link → reconfigure → revoke` order in §7 is an *implementation* sequence inside the node, not a gate edge.)
- **Fully PARALLEL to the DP-2 auth spine** (D3/D1/D2/D5/D7/D6/D8) — the Connector is the cleanest repo on the credential-scope boundary and forms a true side-branch. Nothing in this item gates, or is gated by, the DP-2 envelope work beyond shipped 018.

**Adjacent (not this item):** G4 (Security Gate) is genuinely adjacent — the at-rest secret storage, no-logging, and rotation-safety requirements conform to the existing 003 G4 policy. Per the brief, task tags stay G10/G2/G3; G4-conformance is noted (§8) but not built out.

## Open questions (OQ-n)

- **OQ-1 (Connector-specific).** Pre-expiry warning policy — how far ahead of `dp2_credential_expires_at` should the Connector surface the "request rotation" state, and through what channel (operator UI banner, ops alert, posting-log entry)? *(Plan-phase; the Connector cannot self-rotate, N-5.)*
- **OQ-2 (Connector-specific).** Should a future Connector slice add the DP-2 consistency-CHECK-aligned local invariant (refuse to operate if `dp2_token` is set but `dp2_connector_registration_id` is empty), mirroring the linkage the US4 guard enforces server-side (E-4)?
- **OQ-3 (cross-repo, raise — do not decide here).** Where does the human-operated admin-API client live? `connector-admin.yaml` is session-only (E-2), so issue/rotate/revoke is driven from a human session — most plausibly the **Console** (an 028 §20 Console follow-up: "device management/revocation … audit/support views") or a thin operator tool. This draft assumes the credential is issued *somewhere session-authenticated* and consumed by the Connector; the client's home is a cross-repo routing decision for the owner.

**Carried-forward 028 open questions (NOT auto-decided here):** OQ-2/3/4/9/11 of 028 are POS / offline-PIN scoped and not relevant to the Connector side; they are left open at the 028 boundary and not manufactured into Connector relevance.

---

> **Docs-only record (SPECIFY-ONLY, DRAFT).** This draft coordinates and records the Connector-side adoption of the shipped 018 boundary; it does not implement, define contracts, or create migrations. No implementation is dispatched without explicit, scoped owner approval after G10 verification.
