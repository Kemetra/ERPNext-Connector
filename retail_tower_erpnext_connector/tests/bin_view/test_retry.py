# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-176 — the bounded bin-view retry set (pure; no frappe)."""

from retail_tower_erpnext_connector.connector.bin_view import contracts as c
from retail_tower_erpnext_connector.connector.bin_view import retry as r


def _request(n=1, max_windows=20):
    ref = f"{n:08d}-1111-4111-8111-111111111111"
    return c.BinViewRequest(
        request_ref=ref,
        store_id="33333333-3333-4333-8333-333333333333",
        erpnext_warehouse_ref="ERP-WH-1",
        run_ref="44444444-4444-4444-8444-444444444444",
        item_window=c.BinViewItemWindow(
            window_seq=0, max_items=500, from_item_ref=None, to_item_ref=None, max_windows=max_windows
        ),
        item_cursor=ref,
    )


def test_first_failure_queues_the_request():
    rs = r.RetrySet()
    outcome = rs.record_failure(_request())
    assert outcome == r.FailureOutcome(status=r.QUEUED, failures=1)
    assert _request().request_ref in rs
    assert rs.pending() == [_request()]


def test_abandoned_after_max_retry_ticks_failed_retries():
    rs = r.RetrySet()
    req = _request()
    outcomes = [rs.record_failure(req) for _ in range(r.MAX_RETRY_TICKS + 1)]
    # The original failure + MAX_RETRY_TICKS failed retries are queued; the next one abandons.
    assert [o.status for o in outcomes[:-1]] == [r.QUEUED] * r.MAX_RETRY_TICKS
    assert outcomes[-1].status == r.ABANDONED
    assert req.request_ref not in rs


def test_resolve_forgets_the_request():
    rs = r.RetrySet()
    rs.record_failure(_request())
    rs.resolve(_request().request_ref)
    assert len(rs) == 0
    rs.resolve("unknown")  # no-op


def test_bounded_size_abandons_new_failures_but_keeps_counting_held_ones():
    rs = r.RetrySet()
    for i in range(r.MAX_PENDING):
        rs.record_failure(_request(i))
    assert rs.record_failure(_request(r.MAX_PENDING)).status == r.ABANDONED
    assert len(rs) == r.MAX_PENDING
    assert rs.record_failure(_request(0)).status == r.QUEUED  # already held


def test_state_round_trips_and_tolerates_garbage():
    rs = r.RetrySet()
    rs.record_failure(_request(1))
    rs.record_failure(_request(2, max_windows=None))
    rs.record_failure(_request(2, max_windows=None))
    state = rs.to_state()
    again = r.RetrySet(state)
    assert again.pending() == rs.pending()
    assert again.failures(_request(2).request_ref) == 2

    state["broken"] = {"request": {"nope": 1}, "failures": 1}
    state["mismatch"] = {"request": _request(3).to_wire(), "failures": 1}
    state[_request(4).request_ref] = {"request": _request(4).to_wire(), "failures": 0}
    assert len(r.RetrySet(state)) == 2
    assert len(r.RetrySet(None)) == 0
    assert len(r.RetrySet("not a mapping")) == 0
