# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""T011 — local unit tests for the pull/ack transport behind a Protocol.

The transport (the live HTTP call to DP2) is abstracted behind :class:`HttpTransport`
so the client logic is testable against a fake here; the live two-op round-trip is the
deferred ⏳ BENCH-VALIDATION component. No frappe, no live DP2.
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting import transport as t


def _wire_work_item(external_id: str = "POS-9001") -> dict:
    return {
        "workItemRef": "11111111-1111-4111-8111-111111111111",
        "kind": "sale_post",
        "sourceSystem": "pos-pulse",
        "externalId": external_id,
        "payloadHash": "a" * 64,
        "businessDate": "2026-06-01",
        "itemCursor": "cursor-1",
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


class FakeTransport:
    """A recording fake implementing the HttpTransport Protocol — no real network."""

    def __init__(self, get_response: dict, post_response: dict | None = None):
        self._get_response = get_response
        self._post_response = post_response or {}
        self.get_calls: list[tuple[str, dict, dict]] = []
        self.post_calls: list[tuple[str, dict, dict]] = []

    def get(self, path: str, *, params: dict, headers: dict) -> dict:
        self.get_calls.append((path, params, headers))
        return self._get_response

    def post(self, path: str, *, json: dict, headers: dict) -> dict:
        self.post_calls.append((path, json, headers))
        return self._post_response


class TestPullPostings:
    def test_parses_feed_page_into_work_items(self):
        page = {
            "items": [_wire_work_item("POS-1"), _wire_work_item("POS-2")],
            "cursor": "page-cursor",
            "next_page_token": "next-tok",
        }
        client = t.PostingFeedClient(FakeTransport(get_response=page), correlation_id="req-abc")
        result = client.pull_postings(since="cursor-0")
        assert len(result.items) == 2
        assert all(isinstance(wi, c.PostingWorkItem) for wi in result.items)
        assert result.items[0].external_id == "POS-1"
        assert result.cursor == "page-cursor"
        assert result.next_page_token == "next-tok"

    def test_carries_correlation_id_header(self):
        page = {"items": [], "cursor": "x", "next_page_token": None}
        fake = FakeTransport(get_response=page)
        client = t.PostingFeedClient(fake, correlation_id="req-xyz")
        client.pull_postings(since="cursor-0")
        _path, _params, headers = fake.get_calls[0]
        # spec-003 substrate: the DP2 request_id correlation travels on every call.
        assert headers.get(t.CORRELATION_HEADER) == "req-xyz"

    def test_since_cursor_passed_as_param(self):
        page = {"items": [], "cursor": "x", "next_page_token": None}
        fake = FakeTransport(get_response=page)
        client = t.PostingFeedClient(fake, correlation_id="r")
        client.pull_postings(since="cursor-7")
        _path, params, _headers = fake.get_calls[0]
        assert params.get("since") == "cursor-7"

    def test_empty_page_is_not_an_error(self):
        page = {"items": [], "cursor": "x", "next_page_token": None}
        client = t.PostingFeedClient(FakeTransport(get_response=page), correlation_id="r")
        result = client.pull_postings(since=None)
        assert result.items == ()

    def test_missing_cursor_raises(self):
        # F-011: 012 cursor is required (minLength 1) — empty/absent must raise, not re-baseline.
        page = {"items": [], "cursor": "", "next_page_token": None}
        client = t.PostingFeedClient(FakeTransport(get_response=page), correlation_id="r")
        with pytest.raises(ValueError):
            client.pull_postings(since=None)


class TestAckOutcome:
    def test_posts_outcome_body_and_work_item_ref_in_path(self):
        fake = FakeTransport(get_response={}, post_response={"workItemRef": "wi-1", "outcome": "posted"})
        client = t.PostingFeedClient(fake, correlation_id="req-1")
        ack = c.OutcomeAckRequest.posted(c.ErpnextDocumentRef("Sales Invoice", "ACC-SINV-0001"))
        client.ack_outcome("wi-1", ack)
        path, body, headers = fake.post_calls[0]
        assert "wi-1" in path
        assert body["outcome"] == "posted"
        assert body["documentRef"] == {"doctype": "Sales Invoice", "name": "ACC-SINV-0001"}
        assert headers.get(t.CORRELATION_HEADER) == "req-1"

    def test_ack_sends_idempotency_key_header_when_provided(self):
        fake = FakeTransport(get_response={}, post_response={})
        client = t.PostingFeedClient(fake, correlation_id="r")
        ack = c.OutcomeAckRequest.failed_transient()
        client.ack_outcome("wi-2", ack, idempotency_key="idem-9")
        _path, _body, headers = fake.post_calls[0]
        assert headers.get(t.IDEMPOTENCY_HEADER) == "idem-9"

    def test_does_not_mutate_dp2_sale_fact(self):
        # The client only POSTs the outcome; it never issues a sale-mutating call.
        fake = FakeTransport(get_response={}, post_response={})
        client = t.PostingFeedClient(fake, correlation_id="r")
        client.ack_outcome("wi-3", c.OutcomeAckRequest.failed_transient())
        # Exactly one POST (the ack) and zero GETs — no reach-back, no sale write.
        assert len(fake.post_calls) == 1
        assert len(fake.get_calls) == 0
