# Runbook: Connector Credential Cutover (legacy token → registration-linked credential)

**Spec**: 007 — Connector Admin Counterpart (D10) | **Implements**: spec §7 cutover | **Date**: 2026-06-12

Operational procedure to migrate the connector from a legacy **hand-edited unlinked `dp2_token`** to a
**registration-linked, `connector`-scoped credential** issued via DP-2's 018 admin surface — with **no
lockout window**. See [`../decisions/connector-credential-lifecycle.md`](../decisions/connector-credential-lifecycle.md)
for the why.

> **Timing constraint (the whole reason this runbook exists).** DP-2's tightened US4
> `ConnectorAuthGuard` requires the presented token to be a `connector`-scoped credential linked to a
> non-disabled registration, enforced **at runtime, independently of the deferred DB consistency
> CHECK**. A legacy unlinked token works only until that enforcement reaches the connector's
> environment — after that it gets a breaking **non-disclosing 401**. **This entire cutover MUST
> complete before US4 enforcement is live in the connector's environment.** Confirm the rollout timing
> with the DP-2 team first.

---

## Roles

- **Tenant admin (human)** — operates the session-only 018 admin surface (`connector-admin.yaml` is
  `cookieAuth`-only; a machine bearer is rejected). Drives register / issue / revoke.
- **Connector operator / ops** — runs `bench migrate`, configures Connector Settings, coordinates the window.

The connector machine **never calls the admin surface** — it only *consumes* the issued credential.

## Prerequisites

- DP-2 `origin/main` carries the shipped 018 surface (`connector-admin.yaml`) + migration `0021`
  (the `connector` scope, `connector_registration`, the US4 guard) — re-confirm at cutover time.
- The connector app is deployed at the 007 level (#34/#35/#36 merged) so Connector Settings has the
  lifecycle fields (`dp2_connector_registration_id`, `dp2_credential_id`, `dp2_credential_expires_at`,
  `dp2_credential_warn_days`). Run `bench migrate` on the site if not already applied (additive,
  backward-compatible — the existing `dp2_token`/`dp2_base_url` are untouched).
- A maintenance window agreed with the DP-2 rollout of US4 enforcement (see the timing constraint).

## Procedure (spec §7 — order is load-bearing)

1. **Register the connector instance** *(tenant admin)* — call `tenantAdminRegisterConnectorInstance`
   for the correct `(environment, erpnext_site_ref)`. At most one active registration per tuple
   (the `0021` unique constraint). Record the returned `connector_registration` id.
2. **Issue a linked credential** *(tenant admin)* — call `tenantAdminIssueConnectorCredential` for that
   registration. Capture, from the response shown **exactly once**: the raw `secret`, the
   `credential_id`, and the bounded `expires_at`. **Never log, paste into chat, or screenshot the raw
   secret** (Gate G4 / S-1).
3. **Reconfigure the connector** *(operator)* — in **Connector Settings**, set:
   - `dp2_token` ← the new raw `secret` (Password field),
   - `dp2_connector_registration_id` ← the registration id from step 1,
   - `dp2_credential_id` ← the `credential_id` from step 2,
   - `dp2_credential_expires_at` ← the `expires_at` from step 2,
   - (optional) `dp2_credential_issued_at`, and `dp2_credential_warn_days` if not the default 14.

   Once the registration ref is set, the connector's `posting.credential.unlinked` advisory clears.
4. **Verify under the new credential** *(operator)* — confirm a live
   `connectorPullPostings` + `connectorAckOutcome` round-trip succeeds — i.e. it passes the tightened
   US4 guard (`findActiveConnectorCredentialByTokenId` resolves the linked instance). A poller tick
   that pulls + acks without a 401 is the proof. **Do not proceed to step 5 until this passes.**
5. **Revoke the legacy token** *(tenant admin)* — call `tenantAdminRevokeConnectorCredential` for the
   old hand-edited credential, **only after** step 4 verifies the new one. This ordering guarantees no
   lockout window (the old token stays valid until the new one is proven).

## Rollback

If step 4 verification fails, the **legacy token is not yet revoked** (step 5 is gated on step 4) — the
connector keeps operating on the old token until US4 enforcement forces the issue. Re-check the
Connector Settings values (especially that `dp2_token` is the new secret and the registration/credential
ids match what 018 issued), then re-attempt from step 3. If the new credential cannot be made to verify
before US4 enforcement goes live, escalate to the DP-2 team to hold the enforcement rollout.

## Post-cutover

- The connector now presents a registration-linked credential; rotation is admin-initiated via
  `tenantAdminRotateConnectorCredential` (atomic immediate-revoke) — a rotate swaps `dp2_token` +
  `dp2_credential_id` + `dp2_credential_expires_at` but leaves `dp2_connector_registration_id` unchanged
  (the registration survives rotation). Repeat steps 2–4 (without step 1) for a rotation.
- The pre-expiry warning (`posting.credential.expiring`) will surface in the connector logs
  `dp2_credential_warn_days` ahead of the next expiry — request a rotation then.
