# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""T050/T052 — local unit tests for the reason-category mapper + failure invariants.

Maps connector-internal failure kinds onto the 012 CLOSED RejectionReason.category set
(decision table rows 4-9); an unmapped internal kind RAISES rather than inventing a wire
code (FR-007). Failure messages carry no secrets (Principle V / Gate G4). No frappe.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting import reasons as r


class TestReasonMapping:
    @pytest.mark.parametrize(
        "internal_kind, expected_category",
        [
            (r.FailureKind.CLOSED_PERIOD, "closed_period"),
            (r.FailureKind.VALIDATION, "validation"),
            (r.FailureKind.UNMAPPED_UNIT, "validation"),  # row 5: unmapped unit IS validation
            (r.FailureKind.UNMAPPED_ACCOUNT, "unmapped_account"),
            (r.FailureKind.MISSING_ITEM_REF, "validation"),  # row 8: upstream contract violation
            (r.FailureKind.DISABLED_ITEM, "validation"),  # row 7
            (r.FailureKind.OTHER, "other"),
        ],
    )
    def test_maps_internal_kind_to_closed_category(self, internal_kind, expected_category):
        reason = r.to_rejection_reason(internal_kind, message="detail")
        assert isinstance(reason, c.RejectionReason)
        assert reason.category == expected_category

    def test_unmapped_uom_is_never_its_own_category(self):
        # There is no `unmapped_uom` in the 012 closed set — it must resolve to validation.
        reason = r.to_rejection_reason(r.FailureKind.UNMAPPED_UNIT, message="unit 'box' unmapped")
        assert reason.category == "validation"
        assert reason.category in c.REJECTION_CATEGORIES

    def test_every_failure_kind_maps_into_the_closed_set(self):
        # T050: no FailureKind escapes the closed set; none invents a new wire code.
        for kind in r.FailureKind:
            reason = r.to_rejection_reason(kind, message="m")
            assert reason.category in c.REJECTION_CATEGORIES

    def test_unknown_kind_raises_not_invents(self):
        # An object that isn't a known FailureKind must raise — never a silent "other".
        with pytest.raises(r.UnmappedFailureKind):
            r.to_rejection_reason("totally-unknown", message="m")  # type: ignore[arg-type]


class TestFailureMessageHygiene:
    def test_scrubs_token_like_substrings(self):
        # T052: no secret/token/credential in the outcome message (Gate G4).
        dirty = "auth failed: Bearer sk-secret-abc123 token=deadbeef password=hunter2"
        clean = r.scrub_message(dirty)
        assert "sk-secret-abc123" not in clean
        assert "deadbeef" not in clean
        assert "hunter2" not in clean
        assert "[redacted]" in clean

    def test_preserves_safe_detail(self):
        clean = r.scrub_message("accounting period 2026-Q1 is closed")
        assert "accounting period 2026-Q1 is closed" == clean

    def test_reason_built_through_mapper_is_scrubbed(self):
        reason = r.to_rejection_reason(
            r.FailureKind.OTHER, message="db error token=abcd1234efgh5678"
        )
        assert "abcd1234efgh5678" not in reason.message

    def test_scrubs_json_serialized_secrets(self):
        # F-008: frappe often serializes exceptions as dicts/JSON — the scrubber must catch
        # quoted/JSON forms, not just `key=value`.
        dirty = '{"password": "hunter2", "api_key": "sk_live_abcd1234efgh"}'
        clean = r.scrub_message(dirty)
        assert "hunter2" not in clean
        assert "sk_live_abcd1234efgh" not in clean

    def test_scrubs_sk_underscore_variant(self):
        # F-008: sk_ (underscore) variant, not only sk-.
        clean = r.scrub_message("key leaked: sk_live_deadbeef1234")
        assert "sk_live_deadbeef1234" not in clean
