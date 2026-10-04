# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-176 — the bin-view poller tick and the paged frappe Bin read, against a frappe stand-in.

``poller`` and ``frappe_glue`` import frappe, so they are loaded against a minimal stand-in (the
RT-39 / RT-71 pattern); the real bench run stays a deferred validation step (standing-rules §6).

Covered here: a mid-attempt transport failure is retried on the NEXT tick as a fresh attempt
(new ``attemptRef`` from window 0) even though the cursor has moved on (the stranded-run fix);
a 409 ``window_sequence_conflict`` on a stale attempt is handled without crashing; the bounded
give-up (``bin_view.report.incomplete_abandoned``); the paged limit refusal
(``bin_view.window.limit_exceeded``); and the keyset page read.
"""

import importlib
import sys
import types

import pytest

from retail_tower_erpnext_connector.connector.bin_view import retry as r

_ROOT = "retail_tower_erpnext_connector"
_POLLER = f"{_ROOT}.connector.bin_view.poller"
_GLUE = f"{_ROOT}.connector.bin_view.frappe_glue"
_MISSING = object()
_REF = "11111111-1111-4111-8111-111111111111"
_REF_2 = "22222222-2222-4222-8222-222222222222"


class _Logger:
    def __init__(self):
        self.records = []

    def _log(self, level):
        return lambda record: self.records.append((level, record))

    def __getattr__(self, level):
        return self._log(level)


class _Cache:
    def __init__(self):
        self.values = {}
        self.writes = []  # (key, retry state as stored at the moment of this write)

    def get_value(self, key):
        return self.values.get(key)

    def set_value(self, key, value):
        self.values[key] = value
        self.writes.append((key, self.values.get("rt_bin_view_retry")))


@pytest.fixture
def frappe_stub():
    before = set(sys.modules)
    saved = sys.modules.get("frappe", _MISSING)
    fake = types.ModuleType("frappe")
    fake.exceptions = types.SimpleNamespace()
    fake.log = _Logger()
    fake.logger = lambda *_a, **_k: fake.log
    fake.cache_obj = _Cache()
    fake.cache = lambda: fake.cache_obj
    sys.modules["frappe"] = fake
    yield fake
    for name in set(sys.modules) - before:
        if name.startswith(_ROOT):
            sys.modules.pop(name, None)
            parent, _, child = name.rpartition(".")
            if parent in sys.modules:
                vars(sys.modules[parent]).pop(child, None)
    if saved is _MISSING:
        sys.modules.pop("frappe", None)
    else:
        sys.modules["frappe"] = saved


def _events(fake, name=None):
    events = [(level, rec) for level, rec in fake.log.records if isinstance(rec, dict)]
    return [(level, rec) for level, rec in events if name is None or rec.get("event") == name]


# --- scripted DP2 + fakes -------------------------------------------------------------------------


class _Resp:
    def __init__(self, status=201, body=None):
        self.status = status
        self.headers = {}
        self.body = body or {}


def _wire(ref=_REF, max_windows=20, max_items=500):
    window = {"windowSeq": 0, "maxItems": max_items, "fromItemRef": None, "toItemRef": None}
    if max_windows is not None:
        window["maxWindows"] = max_windows
    return {
        "requestRef": ref,
        "storeId": "33333333-3333-4333-8333-333333333333",
        "erpnextWarehouseRef": "ERP-WH-1",
        "runRef": "44444444-4444-4444-8444-444444444444",
        "itemWindow": window,
        "itemCursor": ref,
    }


class _Dp2:
    """Serves one feed page per tick (``pages``) and scripted POST outcomes (default 201)."""

    def __init__(self, pages, post_outcomes=None):
        self.pages = list(pages)
        self.post_outcomes = list(post_outcomes or [])
        self.gets, self.posts = [], []

    def get(self, path, *, params, headers):
        self.gets.append(params.get("since"))
        if self.pages:
            return self.pages.pop(0)
        return {"items": [], "cursor": params.get("since") or "c-0", "next_page_token": None}

    def post(self, path, *, json, headers):
        self.posts.append({"path": path, "body": json, "key": headers["Idempotency-Key"]})
        if self.post_outcomes:
            outcome = self.post_outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return _Resp(201)


class _Reader:
    def __init__(self, n):
        from retail_tower_erpnext_connector.connector.bin_view.worker import RawBin

        self.bins = [RawBin(item_code=f"ITEM-{i:05d}", actual_qty=1.5, stock_uom="Nos") for i in range(n)]

    def read_bins(self, *, erpnext_warehouse_ref, item_window):
        return self.bins[: item_window.max_items + 1]

    def read_bins_paged(self, *, erpnext_warehouse_ref, page_size, max_rows):
        return self.bins[:max_rows]


class _Clock:
    def now_iso(self):
        return "2026-10-04T08:00:00.000Z"


def _tick(fake, dp2, reader):
    poller = importlib.import_module(_POLLER)
    from retail_tower_erpnext_connector.connector.bin_view.transport import BinViewClient

    poller._build_bin_view_path = lambda: (BinViewClient(dp2, correlation_id="corr"), reader, _Clock())
    before = len(dp2.posts)
    poller.run_bin_view_poll()
    return dp2.posts[before:]


def _page(*items, cursor="c-1"):
    return {"items": list(items), "cursor": cursor, "next_page_token": None}


def _retry_state(fake):
    return r.RetrySet(fake.cache_obj.values.get("rt_bin_view_retry"))


def _seqs(posts):
    return [p["body"]["window"]["windowSeq"] for p in posts]


def _attempts(posts):
    return {p["body"]["window"]["attemptRef"] for p in posts}


# --- AC5: transport failure on window 1 → next tick, fresh attempt from window 0 ------------------


def test_transport_failure_on_window_1_is_retried_next_tick_as_a_fresh_attempt(frappe_stub):
    dp2 = _Dp2([_page(_wire())], post_outcomes=[_Resp(201), ConnectionError("connection reset")])
    reader = _Reader(1037)

    first = _tick(frappe_stub, dp2, reader)
    assert _seqs(first) == [0, 1]
    # The cursor moved past the page — but the request is durable in the retry set.
    assert frappe_stub.cache_obj.values["rt_bin_view_cursor"] == "c-1"
    assert _REF in _retry_state(frappe_stub)
    (level, rec), = _events(frappe_stub, "bin_view.report.retry_scheduled")
    assert level == "warning" and rec["failures"] == 1 and rec["request_ref"] == _REF

    second = _tick(frappe_stub, dp2, reader)
    assert _seqs(second) == [0, 1, 2]
    assert [p["body"]["window"]["isFinal"] for p in second] == [False, False, True]
    assert len(_attempts(second)) == 1
    assert _attempts(second).isdisjoint(_attempts(first))  # a NEW attemptRef (supersede)
    assert second[0]["key"] != first[0]["key"]
    assert len(_retry_state(frappe_stub)) == 0
    assert dp2.gets == [None, "c-1"]  # the feed cursor is not rewound


def test_retry_state_is_saved_before_the_cursor_moves(frappe_stub):
    # The stranded-run fix: when the cursor moves past the page, the failed request is ALREADY
    # durable in the retry set (a crash between the two writes cannot lose it).
    dp2 = _Dp2([_page(_wire())], post_outcomes=[ConnectionError("down")])
    _tick(frappe_stub, dp2, _Reader(3))
    cursor_writes = [state for key, state in frappe_stub.cache_obj.writes if key == "rt_bin_view_cursor"]
    assert len(cursor_writes) == 1
    assert _REF in r.RetrySet(cursor_writes[0])


def test_stale_attempt_409_mid_sequence_is_handled_and_retried(frappe_stub):
    conflict = _Resp(409, {"error": {"code": "window_sequence_conflict", "message": "m"}})
    dp2 = _Dp2([_page(_wire())], post_outcomes=[_Resp(201), conflict])
    reader = _Reader(1037)

    first = _tick(frappe_stub, dp2, reader)  # must not raise
    assert _seqs(first) == [0, 1]
    (_, rec), = _events(frappe_stub, "bin_view.report.retry_scheduled")
    assert rec["reason"] == "window_sequence_conflict"

    second = _tick(frappe_stub, dp2, reader)
    assert _seqs(second) == [0, 1, 2]
    assert len(_retry_state(frappe_stub)) == 0


def test_409_on_window_0_of_a_new_attempt_means_already_complete(frappe_stub):
    conflict = _Resp(409, {"error": {"code": "window_sequence_conflict"}})
    dp2 = _Dp2([_page(_wire())], post_outcomes=[conflict])
    posts = _tick(frappe_stub, dp2, _Reader(1037))
    assert _seqs(posts) == [0]
    assert len(_events(frappe_stub, "bin_view.report.already_complete")) == 1
    assert len(_retry_state(frappe_stub)) == 0
    assert _tick(frappe_stub, dp2, _Reader(1037)) == []  # nothing retried


def test_gives_up_after_max_retry_ticks(frappe_stub):
    dp2 = _Dp2([_page(_wire())], post_outcomes=[ConnectionError("down")] * 50)
    reader = _Reader(3)
    for _ in range(1 + r.MAX_RETRY_TICKS):
        _tick(frappe_stub, dp2, reader)
    abandoned = _events(frappe_stub, "bin_view.report.incomplete_abandoned")
    assert len(abandoned) == 1
    level, rec = abandoned[0]
    assert level == "error" and rec["request_ref"] == _REF and rec["failures"] == r.MAX_RETRY_TICKS + 1
    assert len(_retry_state(frappe_stub)) == 0
    assert _tick(frappe_stub, dp2, reader) == []  # bounded: no further attempts


def test_report_incomplete_is_retried(frappe_stub):
    dp2 = _Dp2([_page(_wire())], post_outcomes=[_Resp(201, {"complete": False})])
    _tick(frappe_stub, dp2, _Reader(3))
    (_, rec), = _events(frappe_stub, "bin_view.report.retry_scheduled")
    assert rec["reason"] == "report_incomplete"
    assert _REF in _retry_state(frappe_stub)


def test_one_failing_request_does_not_block_the_rest_of_the_page(frappe_stub):
    dp2 = _Dp2([_page(_wire(_REF), _wire(_REF_2))], post_outcomes=[ConnectionError("down")])
    posts = _tick(frappe_stub, dp2, _Reader(3))
    assert [p["path"].split("/")[-2] for p in posts] == [_REF, _REF_2]
    state = _retry_state(frappe_stub)
    assert _REF in state and _REF_2 not in state


def test_a_retried_request_re_offered_by_the_feed_is_attempted_once_per_tick(frappe_stub):
    dp2 = _Dp2([_page(_wire()), _page(_wire(), cursor="c-0")], post_outcomes=[ConnectionError("down")])
    reader = _Reader(3)
    _tick(frappe_stub, dp2, reader)
    second = _tick(frappe_stub, dp2, reader)  # retry + a re-baselined feed offering the same ref
    assert len(second) == 1


# --- AC3: above maxWindows x maxItems → nothing reported, limit_exceeded logged -----------------


def test_limit_exceeded_reports_nothing_and_logs(frappe_stub):
    dp2 = _Dp2([_page(_wire(max_windows=2, max_items=500))])
    posts = _tick(frappe_stub, dp2, _Reader(1001))
    assert posts == []
    (level, rec), = _events(frappe_stub, "bin_view.window.limit_exceeded")
    assert level == "error"
    assert rec["request_ref"] == _REF and rec["limit"] == 1000 and rec["warehouse"] == "ERP-WH-1"
    # Deterministic refusal — logged loudly, not retried.
    assert len(_retry_state(frappe_stub)) == 0


# --- AC4 (tick level): v1 unchanged ---------------------------------------------------------------


def test_v1_request_tick_uses_v1_body_and_key(frappe_stub):
    dp2 = _Dp2([_page(_wire(max_windows=None))])
    (post,) = _tick(frappe_stub, dp2, _Reader(3))
    assert "window" not in post["body"]
    assert post["key"] == f"binview-{_REF}"


def test_v1_overflow_still_refuses_and_logs_overflow(frappe_stub):
    dp2 = _Dp2([_page(_wire(max_windows=None))])
    assert _tick(frappe_stub, dp2, _Reader(501)) == []
    assert len(_events(frappe_stub, "bin_view.window.overflow")) == 1
    assert len(_retry_state(frappe_stub)) == 0


def test_v1_transport_failure_is_retried_with_the_same_v1_key(frappe_stub):
    dp2 = _Dp2([_page(_wire(max_windows=None))], post_outcomes=[ConnectionError("down")])
    reader = _Reader(3)
    first = _tick(frappe_stub, dp2, reader)
    second = _tick(frappe_stub, dp2, reader)
    assert [p["key"] for p in first + second] == [f"binview-{_REF}"] * 2
    assert len(_retry_state(frappe_stub)) == 0


# --- frappe_glue: keyset page read --------------------------------------------------------------


class _BinTable:
    def __init__(self, item_codes):
        self.rows = [
            {"item_code": code, "warehouse": "ERP-WH-1", "actual_qty": 2.0, "stock_uom": "Nos"} for code in item_codes
        ] + [{"item_code": "OTHER", "warehouse": "ERP-WH-2", "actual_qty": 1.0, "stock_uom": "Nos"}]
        self.calls = []

    def get_all(self, doctype, *, filters, fields, order_by, limit):
        assert doctype == "Bin" and order_by == "item_code asc"
        assert "valuation_rate" not in fields and "stock_value" not in fields
        self.calls.append({"filters": dict(filters), "limit": limit})
        rows = [row for row in self.rows if row["warehouse"] == filters["warehouse"]]
        if "item_code" in filters:
            op, bound = filters["item_code"]
            assert op == ">"
            rows = [row for row in rows if row["item_code"] > bound]
        rows.sort(key=lambda row: row["item_code"])
        return [{f: row[f] for f in fields} for row in rows[:limit]]


def _glue(frappe_stub, table):
    frappe_stub.get_all = table.get_all
    return importlib.import_module(_GLUE)


def test_paged_read_uses_keyset_pages_and_stops_at_a_short_page(frappe_stub):
    table = _BinTable([f"I-{i:04d}" for i in range(1037)])
    glue = _glue(frappe_stub, table)
    rows = glue.FrappeBinReader().read_bins_paged(erpnext_warehouse_ref="ERP-WH-1", page_size=500, max_rows=10001)
    assert [row.item_code for row in rows] == [f"I-{i:04d}" for i in range(1037)]
    assert [c["limit"] for c in table.calls] == [500, 500, 500]
    assert "item_code" not in table.calls[0]["filters"]
    assert table.calls[1]["filters"]["item_code"] == [">", "I-0499"]
    assert table.calls[2]["filters"]["item_code"] == [">", "I-0999"]
    assert all(c["filters"]["warehouse"] == "ERP-WH-1" for c in table.calls)


def test_paged_read_stops_at_max_rows(frappe_stub):
    table = _BinTable([f"I-{i:04d}" for i in range(20)])
    glue = _glue(frappe_stub, table)
    rows = glue.FrappeBinReader().read_bins_paged(erpnext_warehouse_ref="ERP-WH-1", page_size=4, max_rows=9)
    assert len(rows) == 9
    assert [c["limit"] for c in table.calls] == [4, 4, 1]


def test_paged_read_of_an_exact_multiple_ends_with_an_empty_page(frappe_stub):
    table = _BinTable([f"I-{i:04d}" for i in range(8)])
    glue = _glue(frappe_stub, table)
    rows = glue.FrappeBinReader().read_bins_paged(erpnext_warehouse_ref="ERP-WH-1", page_size=4, max_rows=100)
    assert len(rows) == 8
    assert [c["limit"] for c in table.calls] == [4, 4, 4]


def test_paged_read_of_an_empty_warehouse(frappe_stub):
    table = _BinTable([])
    glue = _glue(frappe_stub, table)
    assert glue.FrappeBinReader().read_bins_paged(erpnext_warehouse_ref="ERP-WH-1", page_size=500, max_rows=10001) == []
    assert len(table.calls) == 1


def test_v1_read_is_unchanged_single_query(frappe_stub):
    table = _BinTable([f"I-{i:04d}" for i in range(600)])
    glue = _glue(frappe_stub, table)
    window = types.SimpleNamespace(max_items=500)
    rows = glue.FrappeBinReader().read_bins(erpnext_warehouse_ref="ERP-WH-1", item_window=window)
    assert len(rows) == 501
    assert table.calls == [{"filters": {"warehouse": "ERP-WH-1"}, "limit": 501}]
