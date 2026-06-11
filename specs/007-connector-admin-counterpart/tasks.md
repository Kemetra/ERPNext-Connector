# Tasks — Draft D9+D10 Connector Admin Counterpart

> **DRAFT — NOT DISPATCHED.** Planning artifact under docs-only Orchestrator. No implementation, no contract, no migration, no gate mutation. Requires explicit scoped owner approval + G10 verification before any sibling-repo dispatch.

**Status:** SPECIFY-ONLY / DRAFT — for owner review. **Date:** 2026-06-11. **Owning repo (post-dispatch):** Retail-Tower-ERP-Next-Connector. **Deciders:** Owner (Ahmed Shaaban).
**Gating label:** gated — owner approval + G10 verification before dispatch.
**Spec:** [./spec.md](./spec.md) · **Plan:** [./plan.md](./plan.md)

> **NO CODE IS AUTHORED HERE.** This is an ordered task list for the OWNING repo to execute *after* dispatch. Each task is tagged with the gate(s) it carries. All DP-2-side artifacts are shipped upstream dependencies (spec E-1/E-3/E-4) — no task edits a DP-2 file. Kernel node: `CON-018-COUNTERPART` (D9+D10 as ONE node).

## Legend

- **[G10]** Identity & Access Boundary Gate — consumed; MUST be verified (auth-touching).
- **[G2]** Contract Gate — consumed; already SATISFIED by shipped 018 (`connector-admin.yaml`, PR #516) + 012 (`posting-feed.yaml`). Conform, do not author.
- **[G3]** Migration Gate — applies to the **Frappe `Connector Settings` DocType delta** only (`bench migrate`), NOT to any SQL migration (`0021` is upstream).
- **(dep: …)** task dependency.

## T0 — Gate preconditions (no code)

- **T0.1 [G10]** Verify 028 §22 boundary decisions are signed and G10 is satisfied for this consumer. **Blocker if unverified.**
- **T0.2 [G2]** Re-read DP-2 `origin/main` at dispatch time; confirm `connector-admin.yaml` + `0021` + `connector-auth.guard.ts` still match the spec's Evidence basis HEADs (snapshot, not live view). *(dep: T0.1)*
- **T0.3 [G10][G2]** Confirm with DP-2 the rollout timing of the tightened US4 `ConnectorAuthGuard` (E-4) into the Connector's environment — the cutover (T3.x) must complete before it. *(dep: T0.2)*

## T1 — Configuration seam (D9) — Frappe DocType delta

- **T1.1 [G3]** Author the additive `Connector Settings` DocType fields: `dp2_connector_registration_id`, `dp2_credential_id`, `dp2_credential_expires_at`, (optional) `dp2_credential_issued_at` — all non-secret; `dp2_token` stays a `Password` field. *(dep: T0.1; spec §5)* — **DocType change, not SQL.**
- **T1.2 [G3]** Author a Docker-free DocType-shape test (mirroring DP-2's `connector-registration-schema-shape.spec.ts` pattern): fields exist, correct types, `dp2_token` still `Password`. *(dep: T1.1)*
- **T1.3 [G3]** Record the bench-gated `bench migrate` round-trip as a deferred bench-validation (standing-rules §6) — idempotent, additive, backward-compatible, tested on non-prod bench (G3 discipline). *(dep: T1.1)*

## T2 — Lifecycle-aware behavior (D9 / G-2) — replace the reactive-only model

- **T2.1** Implement the pre-expiry check (`now()` vs `dp2_credential_expires_at`) surfacing an operator-facing "credential expiring — request rotation" state; the Connector cannot self-rotate (N-5 — warn/prompt only). *(dep: T1.1; spec §6)*
- **T2.2** Preserve the existing 003 §8 401 handling: non-disclosing re-authenticate state, never expose raw/previous token, never blind-retry a 401 as transient. *(dep: T2.1)* — conforms to G4/003 secret discipline (adjacent; noted, not built out).
- **T2.3** Unit tests (injected-fake pattern, like `posting/transport.py` tests): expiry-warning fires near expiry / does not fire otherwise; 401 path surfaces re-auth without token exposure; a rotate swaps secret + `dp2_credential_id` + `dp2_credential_expires_at` but leaves `dp2_connector_registration_id` unchanged. *(dep: T2.1, T2.2)*

## T3 — Cutover (D10) — register-linked credential before US4 enforcement

> Operational + coordinated. The human tenant-admin steps (T3.1, T3.2, T3.5) run against the **session-only** admin surface (E-2) — the Connector never calls it. Order is the spec §7 sequence; it is an implementation sequence inside the single node, NOT a gate edge (D9→D10 REFUTED).

- **T3.1 [G2]** (human tenant-admin) Register the Connector instance via `tenantAdminRegisterConnectorInstance` for the correct `(environment, erpnext_site_ref)` — at most one active per tuple (E-3). *(dep: T0.3)*
- **T3.2 [G2]** (human tenant-admin) Issue a `connector`-scoped credential via `tenantAdminIssueConnectorCredential`; capture the once-shown raw secret + `credential_id` + `expires_at` (E-1). *(dep: T3.1)* — **never log/echo the secret (S-1/N-7).**
- **T3.3 [G3]** (Connector operator) Deploy T1/T2 (so fields exist), then configure `dp2_token` (new secret) + `dp2_connector_registration_id` + `dp2_credential_id` + `dp2_credential_expires_at`. *(dep: T1.3, T2.3, T3.2)*
- **T3.4 [G10][G2]** (verify) Confirm a live `connectorPullPostings` + `connectorAckOutcome` round-trip succeeds under the new linked credential — i.e. it passes the tightened US4 guard (E-4). The existing deferred bench-validation, now with the linked credential. *(dep: T3.3)*
- **T3.5 [G2]** (human tenant-admin) Revoke the legacy hand-edited credential via `tenantAdminRevokeConnectorCredential` — **only after** T3.4 verifies the new one (no lockout window). *(dep: T3.4)*

## T4 — Documentation closeout (owning-repo docs, post-dispatch)

- **T4.1** Update the Connector's own decision/runbook docs (successor to `data-pulse-auth-and-api-policy.md` §8 + `connector-token-scope.md`): the awaited DP-2 `connector` scope + admin surface landed (E-6); lifecycle is now registration-linked + proactively-warned. *(dep: T3.5)* — **owning-repo docs, not authored here.**

## Open-question tasks (do NOT pre-decide — carry to owner)

- **T-OQ1 [G10]** Decide the pre-expiry warning lead time + channel (UI banner / ops alert / posting-log). *(spec OQ-1)*
- **T-OQ2 [G10]** Decide whether to add a local link-invariant (refuse to operate if `dp2_token` set but `dp2_connector_registration_id` empty), mirroring the US4 server-side check (E-4). *(spec OQ-2)*
- **T-OQ3 [cross-repo, owner routing]** Decide where the human-operated admin-API client lives (Console follow-up per 028 §20, or a thin operator tool). NOT a Connector deliverable. *(spec OQ-3)*

## Dependency notes

- **Node-level:** `CON-018-COUNTERPART depends_on [DP-018-IMPL]` — gated **only** on shipped+CLOSED 018 (PR #516 / `0021` + `connector-admin.yaml`). Fully **parallel** to the DP-2 auth spine (D3/D1/D2/D5/D7/D6/D8).
- **Internal:** T1 → T2 → T3 → T4 is an implementation order, not a gate chain. T3.1/T3.2/T3.5 are human-admin steps against the session-only surface; T1/T2/T3.3 are Connector code/config.
- **Cutover timing:** all of T3 must complete before US4 enforcement (E-4) is live in the Connector's environment (T0.3). Brushes G8/G9 rollout; tags held to G10/G2/G3 per brief.

---

> **Docs-only record (SPECIFY-ONLY, DRAFT).** No code, contract, or migration is authored in this task list. Dispatch of any task requires explicit scoped owner approval after G10 verification.
