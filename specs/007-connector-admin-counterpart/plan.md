# Implementation Plan — Draft D9+D10 Connector Admin Counterpart

> **DRAFT — NOT DISPATCHED.** Planning artifact under docs-only Orchestrator. No implementation, no contract, no migration, no gate mutation. Requires explicit scoped owner approval + G10 verification before any sibling-repo dispatch.

**Status:** SPECIFY-ONLY / DRAFT — for owner review. **Date:** 2026-06-11. **Owning repo (post-dispatch):** Retail-Tower-ERP-Next-Connector. **Deciders:** Owner (Ahmed Shaaban).
**Gating label:** gated — owner approval + G10 verification before dispatch.
**Spec:** [./spec.md](./spec.md)

> **For the OWNING repo to execute POST-dispatch.** This is an architecture-altitude phased approach. **No code, Frappe Python, OpenAPI, or SQL is authored here.** All DP-2-side artifacts (`connector-admin.yaml`, `0021`, `ConnectorAuthGuard`) are shipped upstream dependencies (spec E-1/E-3/E-4); this plan conforms to them.

## Constraints carried from the spec

- **N-2/N-3:** author no DP-2 file; build no Connector admin-API client (admin surface is session-only, E-2).
- **N-4:** the 012 posting-feed contract + `connectorBearer` runtime auth are unchanged.
- **G-4/G-5/S-1:** secret stays a `Password` field, captured once, never logged.
- **G3 applies to the Frappe DocType delta only** (`bench migrate`), not SQL — the only SQL migration (`0021`) is upstream.

## Phase 0 — Preconditions (gate verification, no code)

- [G10] Confirm 028 boundary decisions (§22) are signed and G10 is verified for this consumer. *(Hard precondition per `cross-repo-gates.md`.)*
- [G2] Confirm the shipped DP-2 018 contract (`connector-admin.yaml`, PR #516) + 012 `posting-feed.yaml` are the contracts of record — re-read `origin/main` at dispatch time to confirm the HEADs in the spec's Evidence basis still hold (snapshot, not live view).
- Confirm the **rollout coordination** with DP-2: when does the tightened US4 `ConnectorAuthGuard` (E-4) reach the Connector's environment? The whole cutover (Phase 3) must complete before that.

## Phase 1 — Connector configuration seam (D9) — [G3: Frappe DocType delta]

**Goal:** extend `Connector Settings` from a bare hand-edited token to a registration-linked, lifecycle-aware model (spec §5).

- Add the additive non-secret lifecycle fields to the `Connector Settings` Single DocType: `dp2_connector_registration_id`, `dp2_credential_id`, `dp2_credential_expires_at`, (optional) `dp2_credential_issued_at`. `dp2_token` (Password) and `dp2_base_url` are unchanged.
- This is a **Frappe DocType change** applied by `bench migrate` — G3 review discipline (idempotent, reviewed, tested on a non-prod bench, additive/backward-compatible) applies to the DocType delta, **not** to any SQL migration.
- Keep `connector_settings.py` business-logic-light per the repo constitution (Principle VII); lifecycle *reading* helpers (e.g. "is the credential expiring?") may live in a posting/transport-adjacent module, not the DocType class.
- **Test strategy:** a Docker-free DocType-shape test (mirroring DP-2's own `connector-registration-schema-shape.spec.ts` pattern) asserting the new fields exist, types are correct, and `dp2_token` remains a `Password` field; a bench-gated migrate round-trip is a deferred bench-validation (standing-rules §6, the repo's existing pattern).

## Phase 2 — Lifecycle-aware behavior (D9 / G-2) — [no new gate; rides §5 fields]

**Goal:** stop being purely reactive — warn before expiry (spec §6).

- Implement a pre-expiry check comparing `now()` to `dp2_credential_expires_at`; surface an operator-facing "credential expiring — request rotation" state. The Connector **cannot self-rotate** (admin surface is session-only, N-5) — it warns and prompts only.
- Preserve the existing 401 handling (003 §8): non-disclosing refusal → surface re-authenticate state; never expose raw/previous token; never blind-retry a 401 as transient.
- **Test strategy:** unit tests (against the repo's injected-fake pattern, like `posting/transport.py` tests) for: expiry-window warning fires; warning does NOT fire when not near expiry; 401 path still surfaces re-auth without exposing the token; rotate swaps secret + credential id + expiry but leaves `registration_id` unchanged.

## Phase 3 — Cutover (D10) — [rollout-coordinated; tags stay G10/G2/G3]

**Goal:** present a registration-linked `connector`-scoped credential before US4 enforcement is live (spec §7), with no lockout window.

- This phase is **operational + coordinated**, not primarily code: a human tenant-admin drives the session-only admin surface (E-2) — register instance, issue linked credential — and the Connector operator reconfigures + verifies, then the admin revokes the legacy token (spec §7 steps 1–5).
- The only Connector *code* dependency is that Phases 1–2 must be deployed first so the new fields exist to hold the linked credential's refs.
- **Verify gate:** the Connector must pass the tightened US4 guard (`findActiveConnectorCredentialByTokenId` returns the linked instance, E-4) on a live `connectorPullPostings` + `connectorAckOutcome` round-trip — this is the existing deferred bench-validation, now with the linked credential.
- **Rollback:** if Phase 3 verification fails, the legacy token is NOT yet revoked (step 5 is gated on step 4) — the Connector keeps operating on the old token until US4 enforcement forces the issue; re-attempt the cutover.

## Phase 4 — Documentation closeout (no gate)

- Update the Connector's own decision/runbook docs (e.g. a successor note to `data-pulse-auth-and-api-policy.md` §8 and `connector-token-scope.md`) to record that the awaited DP-2 `connector` scope + admin surface landed (E-6) and the lifecycle is now registration-linked + proactively-warned — **owning-repo docs, authored post-dispatch, not here.**

## Gate tag summary

| Phase | Gate tags | Note |
|---|---|---|
| 0 Preconditions | G10, G2 | G10 verify (hard); G2 already satisfied (shipped 018 + 012 contracts). |
| 1 Config seam | G3 | Frappe DocType delta via `bench migrate` — NOT SQL; `0021` is upstream. |
| 2 Lifecycle behavior | — | Rides §5 fields; conforms to 003 G4 secret discipline (adjacent, noted). |
| 3 Cutover | G10, G2, G3 | Rollout-coordinated (brushes G8/G9); tags held to G10/G2/G3 per brief. |
| 4 Docs closeout | — | Owning-repo docs only. |

## Out of scope (re-stated)

- No DP-2 contract / migration / guard edit (shipped upstream — N-2).
- No Connector admin-API client (session-only surface — N-3).
- No posting-feed contract or `connectorBearer` scheme change (N-4).
- No mTLS / signed-request rebuild (028 §15 / OQ-10 — N-6).
- No automated self-rotation (N-5).

---

> **Docs-only record (SPECIFY-ONLY, DRAFT).** This plan describes a post-dispatch approach for the owning repo; it authors no code, contract, or migration. Dispatch requires explicit scoped owner approval after G10 verification.
