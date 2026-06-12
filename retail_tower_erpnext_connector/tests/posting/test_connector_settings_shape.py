# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Docker-free DocType-shape test for the Connector Settings credential-lifecycle delta (007 T1.2).

Spec 007 (Connector Admin Counterpart, D9) extends the ``Connector Settings`` Single DocType
*additively* with non-secret credential-lifecycle fields so the connector can record the
registration-linked credential and warn before expiry (no longer purely reactive — E-5 → §5/§6).

A Frappe DocType is a JSON descriptor; on a real bench ``frappe`` reads it to build the table. We
cannot run ``frappe`` locally (standing-rules §6 — no local bench), but we CAN assert the JSON
descriptor declares the right fields with the right types. This mirrors DP-2's own
``connector-registration-schema-shape.spec.ts`` pattern: validate the schema shape without a DB.

The two failure modes this guards:
  - a new lifecycle field missing or mis-typed (e.g. ``expires_at`` authored as Data, not Datetime);
  - ``dp2_token`` silently demoted from ``Password`` to ``Data`` — a Gate G4 / S-1 secret-discipline
    regression (the raw connectorBearer must stay an encrypted Password field, never plaintext).

This module imports NO frappe — it reads and asserts on the committed JSON only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# The committed DocType descriptor (the deliverable T1.1 edits), located relative to this test so
# the check has no dependency on the working directory or a frappe install.
_DOCTYPE_JSON = (
    Path(__file__).resolve().parents[2]
    / "connector"
    / "doctype"
    / "connector_settings"
    / "connector_settings.json"
)


@pytest.fixture(scope="module")
def doctype() -> dict:
    return json.loads(_DOCTYPE_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fields_by_name(doctype: dict) -> dict[str, dict]:
    return {f["fieldname"]: f for f in doctype["fields"]}


class TestExistingFieldsUnchanged:
    def test_is_single_doctype(self, doctype: dict):
        # Connector Settings is a Single DocType (one config record) — the delta is additive only.
        assert doctype.get("issingle") == 1

    def test_dp2_base_url_stays_data(self, fields_by_name: dict[str, dict]):
        assert fields_by_name["dp2_base_url"]["fieldtype"] == "Data"

    def test_dp2_token_stays_password(self, fields_by_name: dict[str, dict]):
        # S-1 / G-4: the raw connectorBearer secret MUST remain a Password field (encrypted at rest,
        # read via get_password, never logged). A demotion to Data would expose it in plaintext.
        assert fields_by_name["dp2_token"]["fieldtype"] == "Password"


class TestLifecycleFieldsAdded:
    # Spec 007 §5 — the additive non-secret credential-lifecycle seam.
    def test_registration_id_field_present_as_data(self, fields_by_name: dict[str, dict]):
        f = fields_by_name["dp2_connector_registration_id"]
        assert f["fieldtype"] == "Data"

    def test_credential_id_field_present_as_data(self, fields_by_name: dict[str, dict]):
        f = fields_by_name["dp2_credential_id"]
        assert f["fieldtype"] == "Data"

    def test_credential_expires_at_present_as_datetime(self, fields_by_name: dict[str, dict]):
        # Drives the pre-expiry warning (G-2) — must be a Datetime, comparable to now().
        f = fields_by_name["dp2_credential_expires_at"]
        assert f["fieldtype"] == "Datetime"

    def test_credential_issued_at_present_as_datetime(self, fields_by_name: dict[str, dict]):
        f = fields_by_name["dp2_credential_issued_at"]
        assert f["fieldtype"] == "Datetime"


class TestLifecycleFieldsAreNonSecret:
    # §5 / S-2: registration id, credential id, and the timestamps are identifiers/status only —
    # they mirror DP-2's non-secret ConnectorInstance/CredentialStatus projections. ONLY dp2_token
    # is a secret. Guard against a future field being authored as a Password by mistake (over-broad)
    # OR a lifecycle field being the only Password (mis-classification).
    def test_only_dp2_token_is_a_password_field(self, doctype: dict):
        password_fields = [
            f["fieldname"] for f in doctype["fields"] if f.get("fieldtype") == "Password"
        ]
        assert password_fields == ["dp2_token"]
