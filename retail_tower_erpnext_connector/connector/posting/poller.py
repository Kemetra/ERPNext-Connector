# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Posting poller — the scheduled entrypoint (Task D, T093) — ⏳ BENCH-VALIDATION.

Registered as a ``scheduler_events`` cron in ``hooks.py``. On each tick it:

  1. builds the posting dependencies (the 012 client over the spec-003 auth, the Frappe-backed
     idempotency store, the signed UOM map, the pre-resolved warehouse map);
  2. pulls posting pages and processes each via the re-P2b :func:`worker.process_page`,
     binding ``post_valid`` to :func:`frappe_glue.post_work_item` (the live submit→ack path);
  3. lets a :class:`worker.PageDegraded` surface as a logged operational alert (the feed carried a
     contract-violating line) — per-item outcomes were already acked, so this does not lose work.

This is the composition root; it imports ``frappe`` and the glue, so it is validated on a bench,
not locally (standing-rules §6). The dependency-construction (auth/config/maps) reads from
Connector Settings + the signed decisions; the exact wiring is finalised at bench time.
"""

from __future__ import annotations

import frappe

from . import worker
from .frappe_store import FrappePostingLogStore

_LOGGER = "retail_tower_posting"
# A bounded number of pages per tick — the scheduler re-enters on the next cron; idempotency
# makes a mid-loop interruption safe (already-posted items resolve to their recorded documentRef).
_MAX_PAGES_PER_TICK = 20


def run_posting_poll() -> None:
    """Scheduler entrypoint — pull + post + ack one batch of posting pages.

    Conservative by design: bounded pages per tick, no self-retry (a transient ack returns control
    to DP2), and every page's per-item outcomes are recorded before any page-level alert.
    """
    try:
        client, post_valid = _build_posting_path()
    except Exception as exc:  # config/auth not ready — log and skip this tick (no partial work).
        frappe.logger(_LOGGER).warning(
            {"event": "posting.poll.skipped", "reason": _safe(str(exc))}
        )
        return

    ack_client = client  # the same 012 client acks invalid items (re-P2b)
    since: str | None = _load_cursor()
    pages = 0
    while pages < _MAX_PAGES_PER_TICK:
        result = worker.process_page(client, ack_client, since=since, post_valid=post_valid)
        # A degraded page is an ALERT, not a retry: every item on it already reached a terminal
        # outcome (posted or acked-rejected), so we ALWAYS advance the cursor — re-pulling would be
        # the forbidden page-level retry of already-acked items (re-P2b). The breach is surfaced as
        # an operational alert so DP2 can fix the feed contract; polling continues.
        if result.degraded:
            frappe.logger(_LOGGER).error(
                {"event": "posting.feed.degraded", "detail": _safe(result.degraded_message or "")}
            )
        pages += 1
        _save_cursor(result.cursor)  # advance regardless of degraded — all items are terminal
        since = result.cursor
        if result.next_page_token is None:
            break  # caught up — no more pending pages


def _build_posting_path():
    """Construct the 012 client + a bound ``post_valid(work_item)`` callable.

    Wires: the spec-003-authed PostingFeedClient, the Frappe-backed idempotency store, the signed
    UOM map, and the pre-resolved warehouse map — then binds frappe_glue.post_work_item to them.
    Finalised at bench time (reads Connector Settings + signed decisions).
    """
    from .frappe_glue import post_work_item  # local import: glue imports frappe-only symbols
    from .transport import PostingFeedClient
    from .uom import PreResolvedWarehouse, UomMap

    correlation_id = frappe.generate_hash(length=16)
    transport = _build_http_transport()  # auth-backed HTTP client to DP2 (spec 003)
    client = PostingFeedClient(transport, correlation_id=correlation_id)
    store = FrappePostingLogStore()
    uom_map = UomMap(_load_uom_map())
    warehouses = PreResolvedWarehouse(_load_warehouse_map())

    def post_valid(work_item) -> None:
        post_work_item(
            work_item,
            client=client,
            store=store,
            uom_map=uom_map,
            warehouses=warehouses,
            correlation_id=correlation_id,
        )

    return client, post_valid


# --- bench-time wiring stubs (read Connector Settings / signed decisions) --------------------
# These are intentionally thin; their concrete bodies are finalised against the live site at
# bench validation. They raise until configured, so run_posting_poll() skips cleanly (logged)
# rather than posting with half-configured dependencies.


def _build_http_transport():
    raise NotImplementedError("HTTP transport to DP2 is wired from Connector Settings at bench time")


def _load_uom_map() -> dict:
    raise NotImplementedError("unit→UOM map is loaded from the signed decision at bench time")


def _load_warehouse_map() -> dict:
    raise NotImplementedError("store→warehouse map is loaded at bench time")


def _load_cursor() -> str | None:
    return frappe.cache().get_value("rt_posting_cursor")


def _save_cursor(cursor: str) -> None:
    frappe.cache().set_value("rt_posting_cursor", cursor)


def _safe(message: str) -> str:
    from .reasons import scrub_message

    return scrub_message(message)
