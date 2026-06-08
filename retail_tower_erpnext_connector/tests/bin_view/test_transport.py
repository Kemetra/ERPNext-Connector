# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Local unit tests for the 019 bin-view pull/report transport behind a Protocol.

The transport (the live HTTP call to DP2) is abstracted behind :class:`HttpTransport`
so the client logic is testable against a fake here; the live round-trip is the
bench-validated component. No frappe, no live DP2.
"""

import pytest

from retail_tower_erpnext_connector.connector.bin_view import contracts as c
from retail_tower_erpnext_connector.connector.bin_view import transport as t


def _wire_request(request_ref: str = "11111111-1111-4111-8111-111111111111") -> dict:
    return {
        "requestRef": request_ref,
        "storeId": "33333333-3333-4333-8333-333333333333",
        "erpnextWarehouseRef": "ERP-WH-1",
        "runRef": "44444444-4444-4444-8444-444444444444",
        "itemWindow": {
            "windowSeq": 0,
            "maxItems": 500,
            "fromItemRef": None,
            "toItemRef": None,
        },
        "itemCursor": request_ref,
    }


class _Resp:
    def __init__(self, status: int, headers: dict | None = None, body: dict | None = None):
        self.status = status
        self.headers = headers or {}
        self.body = body or {}


class FakeTransport:
    """A recording fake implementing the HttpTransport Protocol — no real network."""

    def __init__(self, get_response: dict, post_response: object = None):
        self._get_response = get_response
        self._post_response = post_response
        self.calls: list[tuple[str, str, dict, dict]] = []

    def get(self, path: str, *, params: dict, headers: dict) -> dict:
        self.calls.append(("GET", path, params, headers))
        return self._get_response

    def post(self, path: str, *, json: dict, headers: dict) -> object:
        self.calls.append(("POST", path, json, headers))
        return self._post_response


def _client(transport) -> t.BinViewClient:
    return t.BinViewClient(transport, correlation_id="corr-1")


# --- pull_requests --------------------------------------------------------------------


def test_pull_requests_parses_page_and_sends_opaque_cursor():
    fake = FakeTransport(
        {"items": [_wire_request()], "cursor": "cur-2", "next_page_token": "cur-2"}
    )
    page = _client(fake).pull_requests(since="cur-1", limit=50)

    assert len(page.items) == 1
    req = page.items[0]
    assert req.request_ref == "11111111-1111-4111-8111-111111111111"
    assert req.erpnext_warehouse_ref == "ERP-WH-1"
    assert req.run_ref == "44444444-4444-4444-8444-444444444444"
    assert req.item_window.window_seq == 0
    assert req.item_window.max_items == 500
    assert page.cursor == "cur-2"
    assert page.next_page_token == "cur-2"
    # The opaque `since` cursor is sent verbatim, limit capped.
    _, _, params, headers = fake.calls[0]
    assert params["since"] == "cur-1"
    assert params["limit"] == 50
    assert headers[t.CORRELATION_HEADER] == "corr-1"


def test_pull_requests_empty_page_is_valid():
    fake = FakeTransport({"items": [], "cursor": "cur-1", "next_page_token": None})
    page = _client(fake).pull_requests(since=None)
    assert page.items == ()
    assert page.next_page_token is None


def test_pull_requests_caps_limit_at_500():
    fake = FakeTransport({"items": [], "cursor": "c", "next_page_token": None})
    _client(fake).pull_requests(since=None, limit=9999)
    assert fake.calls[0][2]["limit"] == 500


def test_pull_requests_missing_cursor_raises():
    fake = FakeTransport({"items": [], "cursor": "", "next_page_token": None})
    with pytest.raises(ValueError):
        _client(fake).pull_requests(since=None)


# --- report_snapshot ------------------------------------------------------------------


def _report() -> c.BinViewSnapshotReport:
    return c.BinViewSnapshotReport(
        entries=(c.BinEntry(erpnext_item_ref="ITEM-A", quantity="12.500000", stock_uom="Nos"),),
        read_at="2026-06-08T10:00:00.000Z",
    )


def test_report_snapshot_201_records_and_sends_idempotency_key():
    fake = FakeTransport({}, _Resp(201, body={"requestRef": "r"}))
    result = _client(fake).report_snapshot("req-1", _report(), idempotency_key="idem-1")
    assert result.recorded is True
    assert result.replayed is False
    method, path, body, headers = fake.calls[0]
    assert method == "POST"
    assert path == "/api/connector/v1/erpnext/bin-view-requests/req-1/snapshot"
    assert headers[t.IDEMPOTENCY_HEADER] == "idem-1"
    # The body carries exact-decimal quantity STRING + stockUom, NO valuation.
    assert body["entries"][0]["quantity"] == "12.500000"
    assert body["entries"][0]["stockUom"] == "Nos"
    assert body["entries"][0]["erpnextItemRef"] == {"doctype": "Item", "name": "ITEM-A"}


def test_report_snapshot_200_replay_flag():
    fake = FakeTransport({}, _Resp(200, headers={"Idempotent-Replayed": "true"}, body={}))
    result = _client(fake).report_snapshot("req-1", _report(), idempotency_key="idem-1")
    assert result.recorded is True
    assert result.replayed is True


def test_report_snapshot_409_raises_conflict():
    fake = FakeTransport({}, _Resp(409, body={"code": "idempotency_key_conflict"}))
    with pytest.raises(t.ReportConflict):
        _client(fake).report_snapshot("req-1", _report(), idempotency_key="idem-1")


def test_report_snapshot_404_raises_not_found():
    fake = FakeTransport({}, _Resp(404, body={"code": "not_found"}))
    with pytest.raises(t.ReportNotFound):
        _client(fake).report_snapshot("req-1", _report(), idempotency_key="idem-1")


def test_report_snapshot_unexpected_status_raises():
    fake = FakeTransport({}, _Resp(500, body={"code": "system_failure"}))
    with pytest.raises(RuntimeError):
        _client(fake).report_snapshot("req-1", _report(), idempotency_key="idem-1")
