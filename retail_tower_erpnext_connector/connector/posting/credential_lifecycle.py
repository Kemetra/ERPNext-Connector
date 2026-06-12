# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Pure credential-lifecycle helpers (spec 007 — Connector Admin Counterpart, D9 / G-2).

Today the connector is purely *reactive* about its DP2 credential (E-5): the only signal of a
credential problem is a 401 on a live pull/ack. Spec 007 records the credential's bounded
``expires_at`` in Connector Settings (§5) so the connector can be *proactive* — compare ``now()``
to the expiry and surface an operator-facing 'credential expiring — request rotation' state BEFORE
a 401 ever fires (§6, Goal G-2).

The connector CANNOT self-rotate: the 018 admin surface that mints credentials is human-session-only
(N-5). These helpers only *evaluate* lifecycle state and *apply* a rotation the operator/admin
performed out-of-band; they never call DP2 and never mint a credential.

Design — time is INJECTED, not read from a hidden clock:
  - ``evaluate_expiry`` takes ``now`` and ``expires_at`` as explicit ``datetime`` params, so the
    warning-window boundary is deterministically testable (the ``posting/transport.py`` injected-fake
    pattern). The bench-only poller shell passes ``frappe.utils.now_datetime()``.

Secret discipline (S-1 / Gate G4): these helpers are NEVER given the raw token. They operate on the
NON-secret lifecycle fields only (registration id, credential id, expiry) — so no operator-facing
message can leak a secret.

This module imports NO frappe.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

# OQ-1 is a plan-phase decision (how far ahead to warn + through what channel). The helper takes the
# lead time as a parameter with a documented default so the policy is explicit, not hard-coded.
DEFAULT_WARN_WITHIN = timedelta(days=14)


class CredentialExpiryStatus(str, Enum):
    """The lifecycle state derived from the recorded ``expires_at`` (§6).

    ``UNKNOWN`` is distinct from ``ACTIVE``: a legacy / not-yet-reconfigured credential has no
    recorded expiry (E-5) — we cannot *prove* it is healthy, so we do not claim ``ACTIVE`` (a
    missing expiry must never masquerade as a healthy credential — Principle VI). It simply cannot
    be warned-on proactively and falls back to the reactive 401 path.
    """

    ACTIVE = "active"
    EXPIRY_WARNING = "expiry_warning"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CredentialExpiryState:
    """The evaluated expiry state + the operator-facing surfacing decision (§6)."""

    status: CredentialExpiryStatus
    should_warn: bool
    message: str


class CredentialAuthStatus(str, Enum):
    """The reactive auth state derived from a live pull/ack result (003 §8).

    Independent of :class:`CredentialExpiryStatus`: a credential revoked or disabled BEFORE its
    recorded expiry (admin revoke / disabled instance — E-4) yields a 401 while ``evaluate_expiry``
    would still report ``ACTIVE``. Both signals must coexist (§6 has two distinct 401 transitions).
    """

    OK = "ok"
    AUTH_FAILED = "auth_failed"


@dataclass(frozen=True)
class CredentialAuthState:
    """The surfacing decision for a live auth result (003 §8 obligations)."""

    status: CredentialAuthStatus
    reauthenticate_required: bool
    retryable: bool
    message: str


def classify_auth_failure(*, operation: str) -> CredentialAuthState:
    """Classify a non-disclosing 401 on a live pull/ack into a re-authenticate state (003 §8, T2.2).

    Preserves the existing 003 §8 obligations exactly:
      1. surface a clear operator-facing **re-authenticate** state;
      2. never expose the raw/previous token or any credential in the message (S-1 / G-4);
      3. never treat the 401 as transient — ``retryable=False``, no blind retry.

    The 401 body is non-disclosing (it does not distinguish revoked / invalid / missing-binding —
    auth-policy §8), so the surfaced message MUST NOT invent a specific cause it cannot know. The
    classifier is given only the ``operation`` ("pull"/"ack") for the operator log — never a token.
    """
    return CredentialAuthState(
        status=CredentialAuthStatus.AUTH_FAILED,
        reauthenticate_required=True,
        retryable=False,
        message=(
            f"DP2 refused the connector credential on {operation} (401, non-disclosing) — "
            "re-authenticate: have the tenant admin re-provision / rotate the connector credential, "
            "then reconfigure Connector Settings. Not retried (a 401 is a credential problem, "
            "not a transient)."
        ),
    )


@dataclass(frozen=True)
class CredentialRefs:
    """The non-secret registration-linked credential refs recorded in Connector Settings (§5).

    Immutable: a rotation produces a NEW instance (:func:`apply_rotation`), never a mutation — so a
    caller holding the pre-rotation refs is unaffected (repo immutable-by-default style).
    """

    registration_id: str
    credential_id: str
    expires_at: datetime | None


def evaluate_expiry(
    *,
    now: datetime,
    expires_at: datetime | None,
    warn_within: timedelta = DEFAULT_WARN_WITHIN,
    credential_id: str | None = None,
) -> CredentialExpiryState:
    """Classify the credential's expiry state and decide whether to surface an operator warning.

    - no recorded ``expires_at`` → ``UNKNOWN`` (cannot warn proactively — reactive fallback);
    - ``now`` past ``expires_at`` → ``EXPIRED`` (warn — the next live call will 401, E-4);
    - within ``warn_within`` of expiry (inclusive) → ``EXPIRY_WARNING`` (warn — request rotation);
    - otherwise → ``ACTIVE`` (no warning).

    The ``message`` names the credential by its NON-secret id only — never the raw token (S-1/G-4).
    """
    cred = credential_id or "(unrecorded)"

    if expires_at is None:
        return CredentialExpiryState(
            status=CredentialExpiryStatus.UNKNOWN,
            should_warn=False,
            message=(
                f"DP2 credential {cred} has no recorded expiry — cannot warn before expiry; "
                "reconfigure Connector Settings with the issued credential's expires_at (007 §5)."
            ),
        )

    if now >= expires_at:
        return CredentialExpiryState(
            status=CredentialExpiryStatus.EXPIRED,
            should_warn=True,
            message=(
                f"DP2 credential {cred} expired at {expires_at.isoformat()} — request rotation; "
                "live pull/ack will be refused (non-disclosing 401)."
            ),
        )

    if expires_at - now <= warn_within:
        return CredentialExpiryState(
            status=CredentialExpiryStatus.EXPIRY_WARNING,
            should_warn=True,
            message=(
                f"DP2 credential {cred} expires at {expires_at.isoformat()} — request rotation "
                "from the tenant admin before it lapses (the connector cannot self-rotate)."
            ),
        )

    return CredentialExpiryState(
        status=CredentialExpiryStatus.ACTIVE,
        should_warn=False,
        message=f"DP2 credential {cred} active until {expires_at.isoformat()}.",
    )


def apply_rotation(
    refs: CredentialRefs,
    *,
    new_credential_id: str,
    new_expires_at: datetime | None,
) -> CredentialRefs:
    """Apply an out-of-band rotation: swap credential id + expiry, KEEP the registration id (§6).

    The ``connector_registration`` is the stable per-tenant identity that survives credential
    rotation (E-1/E-3). The US4 guard resolves the active credential by token id back to that
    registration (E-4), so the registration link MUST NOT change on rotate — clearing it would
    orphan the instance. Returns a NEW :class:`CredentialRefs`; never mutates the input.
    """
    return replace(refs, credential_id=new_credential_id, expires_at=new_expires_at)
