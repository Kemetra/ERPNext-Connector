# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""re-P2b worker loop — local unit tests (Task A).

Per the ratified re-P2b decision (hybrid isolate + raise-after): a feed page line missing
`erpnextItemRef` is a TERMINAL validation rejection for that work item only — the connector
acks it `permanently_rejected`/`validation`, the valid items on the same page still process,
and the page is marked degraded with an operational alert raised AFTER per-item outcomes are
recorded (never an abort that strands valid or already-acked items). No frappe.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting import transport as t
from retail_tower_erpnext_connector.connector.posting import worker as w


def _good_item(external_id: str) -> dict:
    return {
        "workItemRef": f"wi-{external_id}",
        "kind": "sale_post",
        "sourceSystem": "pos-pulse",
        "externalId": external_id,
        "payloadHash": "a" * 64,
        "businessDate": "2026-06-01",
        "itemCursor": f"cur-{external_id}",
        "sale": {
            "saleRef": "22222222-2222-4222-8222-222222222222",
            "storeId": "33333333-3333-4333-8333-333333333333",
            "currencyCode": "EGP",
            "posTotal": "100.00",
            "occurredAt": "2026-06-01T10:00:00Z",
            "businessDate": "2026-06-01",
            "sourceSystem": "pos-pulse",
            "externalId": external_id,
            "lines": [
                {
                    "lineName": "Item A",
                    "unitPrice": "100.00",
                    "currencyCode": "EGP",
                    "quantity": "1",
                    "lineAmount": "100.00",
                    "unit": "each",
                    "erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
                }
            ],
        },
    }


def _bad_item(external_id: str) -> dict:
    """A line missing erpnextItemRef — the upstream contract violation (re-P2b)."""
    item = _good_item(external_id)
    del item["sale"]["lines"][0]["erpnextItemRef"]
    return item


class RecordingClient:
    """A fake PostingFeedClient: records acks, never hits the network."""

    def __init__(self):
        self.acks: list[tuple[str, str, str | None]] = []  # (work_item_ref, outcome, category)

    def ack_outcome(self, work_item_ref, ack, *, idempotency_key=None):
        cat = ack.reason.category if ack.reason else None
        self.acks.append((work_item_ref, ack.outcome, cat))
        return {}


class TestPullPostingsRawIsolation:
    def test_valid_items_parsed_invalid_isolated(self):
        # transport must NOT abort the page on a bad line — it returns valid items parsed and
        # invalid raw entries separately (re-P2b).
        page = {
            "items": [_good_item("A"), _bad_item("B"), _good_item("C")],
            "cursor": "page-1",
            "next_page_token": None,
        }

        class FakeTransport:
            def get(self, path, *, params, headers):
                return page

            def post(self, path, *, json, headers):
                return {}

        client = t.PostingFeedClient(FakeTransport(), correlation_id="r")
        result = client.pull_postings_raw(since=None)
        assert len(result.items) == 2  # A and C parsed
        assert {wi.external_id for wi in result.items} == {"A", "C"}
        assert len(result.invalid) == 1  # B isolated
        assert result.invalid[0].error_kind == "missing_erpnext_item_ref"
        assert result.cursor == "page-1"


class TestWorkerReP2b:
    def test_bad_item_acked_rejected_good_items_continue_page_degraded_returns_advancing(self):
        page = {
            "items": [_good_item("A"), _bad_item("B"), _good_item("C")],
            "cursor": "page-1",
            "next_page_token": None,
        }

        class FakeTransport:
            def get(self, path, *, params, headers):
                return page

            def post(self, path, *, json, headers):
                return {}

        client = t.PostingFeedClient(FakeTransport(), correlation_id="r")
        recording = RecordingClient()
        posted = []

        def poster(wi):
            posted.append(wi.external_id)

        # re-P2b: the worker posts valid items, acks bad ones, and RETURNS a degraded result
        # (it does NOT raise) — every item reached a terminal outcome, so the cursor must advance.
        result = w.process_page(client, recording, since=None, post_valid=poster)

        assert posted == ["A", "C"]  # valid items processed
        assert ("wi-B", "permanently_rejected", "validation") in recording.acks  # bad item rejected
        assert result.degraded is True
        assert result.cursor == "page-1"  # cursor advances — no page-level retry of acked items
        assert "wi-B" in result.degraded_message  # alert names the bad item
        assert result.rejected_refs == ("wi-B",)

    def test_clean_page_does_not_raise(self):
        page = {
            "items": [_good_item("A"), _good_item("C")],
            "cursor": "page-1",
            "next_page_token": None,
        }

        class FakeTransport:
            def get(self, path, *, params, headers):
                return page

            def post(self, path, *, json, headers):
                return {}

        client = t.PostingFeedClient(FakeTransport(), correlation_id="r")
        recording = RecordingClient()
        posted = []
        result = w.process_page(client, recording, since=None, post_valid=lambda wi: posted.append(wi.external_id))
        assert posted == ["A", "C"]
        assert result.degraded is False
        assert result.cursor == "page-1"

    def test_never_substitutes_item_identity(self):
        # The worker must NOT resolve/search/create/substitute — a bad line is rejected, full stop.
        page = {"items": [_bad_item("B")], "cursor": "page-1", "next_page_token": None}

        class FakeTransport:
            def get(self, path, *, params, headers):
                return page

            def post(self, path, *, json, headers):
                return {}

        client = t.PostingFeedClient(FakeTransport(), correlation_id="r")
        recording = RecordingClient()
        posted = []
        result = w.process_page(client, recording, since=None, post_valid=lambda wi: posted.append(wi))
        assert posted == []  # nothing posted; no substitute item invented
        assert recording.acks == [("wi-B", "permanently_rejected", "validation")]
        assert result.degraded is True
        assert result.cursor == "page-1"  # advances even when the whole page was bad
