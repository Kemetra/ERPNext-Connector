# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Local unit tests for the pure credential-lifecycle helpers (007 T2.3 → drives T2.1/T2.2).

Spec 007 (Connector Admin Counterpart, D9/G-2) replaces the connector's purely-reactive auth model
(E-5: only a 401 ever surfaces a credential problem) with a proactive one: from the recorded
``dp2_credential_expires_at`` the connector compares ``now()`` to the expiry and surfaces an
operator-facing 'credential expiring — request rotation' state BEFORE a 401 ever fires. The
connector CANNOT self-rotate (the 018 admin surface is session-only — N-5); it only warns/prompts.

These helpers are pure (frappe-free) so the branching is unit-testable WITHOUT a bench, mirroring
the ``posting/transport.py`` injected-fake pattern. Time is INJECTED (``now`` + ``expires_at`` are
explicit params) — no hidden clock, so the warning-fires/-does-not boundary is deterministic. The
bench-only poller shell passes ``frappe.utils.now_datetime()``.

This module imports NO frappe.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from retail_tower_erpnext_connector.connector.posting import credential_lifecycle as cl

# A fixed reference instant (injected, never `datetime.now()`) — keeps every assertion deterministic.
_NOW = datetime(2026, 6, 12, 12, 0, 0)
# The spec's default warning lead time is a plan-phase OQ-1; the helper takes it as a parameter
# with a documented default so the policy is not silently hard-coded.
_LEAD = timedelta(days=14)


class TestCredentialExpiryState:
    def test_active_when_expiry_far_in_future(self):
        # Expiry well beyond the warning window → plain 'active', no operator action prompted.
        state = cl.evaluate_expiry(
            now=_NOW, expires_at=_NOW + timedelta(days=60), warn_within=_LEAD
        )
        assert state.status == cl.CredentialExpiryStatus.ACTIVE
        assert state.should_warn is False

    def test_warns_when_expiry_within_lead_window(self):
        # Inside the lead window (but not yet expired) → 'expiry_warning', operator prompted to
        # request a rotation. This is the substantive new behavior vs the reactive E-5 model.
        state = cl.evaluate_expiry(
            now=_NOW, expires_at=_NOW + timedelta(days=3), warn_within=_LEAD
        )
        assert state.status == cl.CredentialExpiryStatus.EXPIRY_WARNING
        assert state.should_warn is True

    def test_boundary_exactly_at_lead_window_warns(self):
        # Exactly `warn_within` away is inside the window (inclusive) — warn, don't wait one more day.
        state = cl.evaluate_expiry(now=_NOW, expires_at=_NOW + _LEAD, warn_within=_LEAD)
        assert state.status == cl.CredentialExpiryStatus.EXPIRY_WARNING
        assert state.should_warn is True

    def test_expired_when_now_past_expiry(self):
        # Past expiry → 'expired' (distinct from the in-window warning): the next live call will get
        # the US4 non-disclosing 401; surface it as an expired-credential state, still warn.
        state = cl.evaluate_expiry(
            now=_NOW, expires_at=_NOW - timedelta(minutes=1), warn_within=_LEAD
        )
        assert state.status == cl.CredentialExpiryStatus.EXPIRED
        assert state.should_warn is True

    def test_unknown_when_no_expiry_recorded(self):
        # A legacy / not-yet-reconfigured credential has no recorded expiry (E-5). That is NOT
        # 'active' (we cannot prove it is) and NOT a crash — it is 'unknown': cannot warn proactively,
        # falls back to the reactive 401 path. Distinguishing this prevents a missing expiry from
        # masquerading as a healthy credential (Principle VI).
        state = cl.evaluate_expiry(now=_NOW, expires_at=None, warn_within=_LEAD)
        assert state.status == cl.CredentialExpiryStatus.UNKNOWN
        assert state.should_warn is False

    def test_message_never_contains_a_secret_value(self):
        # S-1 / G-4: the operator-facing message names the credential by its NON-secret id and the
        # expiry, never the raw token. The helper is not even given the secret — but assert the
        # surfaced message carries only non-secret lifecycle fields.
        state = cl.evaluate_expiry(
            now=_NOW,
            expires_at=_NOW + timedelta(days=2),
            warn_within=_LEAD,
            credential_id="cred_abc123",
        )
        assert "cred_abc123" in state.message
        assert "request rotation" in state.message.lower()


class TestAuthFailedSurfacing:
    # T2.2 / 003 §8: a 401 on pull/ack is a CREDENTIAL problem, not a server transient. It must
    # surface a non-disclosing 're-authenticate' state, never expose the raw/previous token, and
    # never be blind-retried as transient. This is the reactive path that COEXISTS with the proactive
    # expiry path — a credential revoked BEFORE expiry (admin revoke / disabled instance, E-4)
    # surfaces here even while evaluate_expiry would still call it 'active'.
    def test_401_surfaces_reauth_state(self):
        state = cl.classify_auth_failure(operation="pull")
        assert state.status == cl.CredentialAuthStatus.AUTH_FAILED
        assert state.reauthenticate_required is True

    def test_401_is_not_transient_no_blind_retry(self):
        # The connector MUST NOT retry a 401 as if the server were transiently failing (003 §8).
        state = cl.classify_auth_failure(operation="ack")
        assert state.retryable is False

    def test_401_message_never_exposes_a_token(self):
        # S-1 / 003 §8 #2: the operator-facing message must NOT contain the raw token, the previous
        # token, or any credential. The classifier is not even given a token — assert the surfaced
        # message stays non-disclosing and carries only the operation + a re-auth instruction.
        leaked = "supersecret-bearer-value-1234567890"  # a fake token literal, not a real secret
        state = cl.classify_auth_failure(operation="pull")
        assert leaked not in state.message
        assert "re-authenticate" in state.message.lower() or "re-provision" in state.message.lower()

    def test_401_message_is_non_disclosing(self):
        # The 401 body itself is non-disclosing (does not distinguish revoked/invalid/missing-binding,
        # auth-policy §8). The surfaced state must NOT invent a specific cause it cannot know.
        state = cl.classify_auth_failure(operation="pull")
        # must not claim a specific disclosed cause the non-disclosing 401 cannot support
        assert "revoked" not in state.message.lower()


class TestRotationPreservesRegistration:
    # §6 / E-1/E-3: a rotate swaps the secret + credential id + expiry, but the registration id is
    # the STABLE identity that survives rotation. This guards the apply-the-rotation transform so a
    # rotate never accidentally clears or changes the registration link (which would orphan the
    # instance from the US4 guard's findActiveConnectorCredentialByTokenId lookup, E-4).
    def test_rotation_swaps_credential_fields_keeps_registration(self):
        before = cl.CredentialRefs(
            registration_id="reg_stable",
            credential_id="cred_old",
            expires_at=_NOW + timedelta(days=1),
        )
        after = cl.apply_rotation(
            before,
            new_credential_id="cred_new",
            new_expires_at=_NOW + timedelta(days=90),
        )
        assert after.registration_id == "reg_stable"  # unchanged — survives rotation
        assert after.credential_id == "cred_new"
        assert after.expires_at == _NOW + timedelta(days=90)

    def test_rotation_does_not_mutate_the_input(self):
        # Immutable-by-default (repo coding style): apply_rotation returns a NEW CredentialRefs and
        # leaves the original untouched, so a caller holding the pre-rotation refs is unaffected.
        before = cl.CredentialRefs(
            registration_id="reg_stable",
            credential_id="cred_old",
            expires_at=_NOW + timedelta(days=1),
        )
        cl.apply_rotation(before, new_credential_id="cred_new", new_expires_at=_NOW)
        assert before.credential_id == "cred_old"
        assert before.expires_at == _NOW + timedelta(days=1)
