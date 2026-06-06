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
    from .config import require_configured_maps
    from .frappe_glue import post_work_item  # local import: glue imports frappe-only symbols
    from .transport import PostingFeedClient
    from .uom import PreResolvedWarehouse, StoreCustomerMap, UomMap

    correlation_id = frappe.generate_hash(length=16)
    settings = frappe.get_doc("Connector Settings")  # one read; child tables + Password live here

    # Parse the maps, then GATE: a fully-empty required map means the connector is not yet
    # configured (every work-item has a store + >=1 line, so an empty map would 100%-reject). Raise
    # so run_posting_poll catches it → posting.poll.skipped, sales stay pending — NOT mass-rejected
    # to DP2's DLQ (Codex PR #23 P1). A populated-but-incomplete map is NOT gated here: a specific
    # absent key is a genuine per-item terminal rejection downstream (decision-table rows 5/8).
    uom = _load_uom_map(settings)
    warehouse = _load_warehouse_map(settings)
    customer = _load_store_customer_map(settings)
    require_configured_maps(uom=uom, warehouse=warehouse, customer=customer)

    transport = _build_http_transport(settings)  # auth-backed HTTP client to DP2 (spec 003)
    client = PostingFeedClient(transport, correlation_id=correlation_id)
    store = FrappePostingLogStore()
    uom_map = UomMap(uom)
    warehouses = PreResolvedWarehouse(warehouse)
    customers = StoreCustomerMap(customer)  # F-009

    def post_valid(work_item) -> None:
        post_work_item(
            work_item,
            client=client,
            store=store,
            uom_map=uom_map,
            warehouses=warehouses,
            customers=customers,
            correlation_id=correlation_id,
        )

    return client, post_valid


# --- Connector Settings wiring ---------------------------------------------------------------
# These read the Connector Settings single DocType (base-URL + token + the three mapping child
# tables). A missing base-URL/token raises, which run_posting_poll() catches → logs
# `posting.poll.skipped` and skips the tick (no posting with a half-configured connector). The
# pure parse logic lives in config.py (unit-tested locally); these are the thin frappe shell.


class _Resp:
    """Status-aware response wrapper so PostingFeedClient._interpret_ack can read 201/200/409/404."""

    def __init__(self, r) -> None:
        self.status = r.status_code
        self.headers = dict(r.headers)
        try:
            self.body = r.json()
        except Exception:
            self.body = {}


class _RequestsTransport:
    """Concrete HttpTransport to DP2 over the spec-003 connectorBearer (Authorization: Bearer).

    Bench-only (imports ``requests``, carries the secret token). GET raises for HTTP errors; POST
    returns a status-aware :class:`_Resp` so the client distinguishes 201/200-replay/409/404.
    """

    def __init__(self, base: str, token: str) -> None:
        self._base = base.rstrip("/")
        self._auth = {"Authorization": "Bearer " + token}

    def get(self, path: str, *, params: dict, headers: dict) -> dict:
        import requests

        r = requests.get(
            self._base + path, params=params, headers={**self._auth, **headers}, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def post(self, path: str, *, json: dict, headers: dict):
        import requests

        r = requests.post(
            self._base + path, json=json, headers={**self._auth, **headers}, timeout=30
        )
        return _Resp(r)


def _build_http_transport(settings) -> _RequestsTransport:
    """Construct the auth-backed transport from Connector Settings (Gate G4 — token via get_password).

    Raises if base-URL or token is unset, so the tick skips cleanly rather than posting blind.
    """
    base_url = (settings.dp2_base_url or "").strip()
    token = settings.get_password("dp2_token")  # decrypted; never get_single_value (masks it)
    if not base_url or not token:
        raise ValueError("Connector Settings: dp2_base_url and dp2_token are required")
    return _RequestsTransport(base_url, token)


def _load_uom_map(settings) -> dict:
    from .config import parse_uom_map

    return parse_uom_map(settings.uom_map)


def _load_warehouse_map(settings) -> dict:
    from .config import parse_warehouse_map

    return parse_warehouse_map(settings.warehouse_map)


def _load_store_customer_map(settings) -> dict:
    from .config import parse_store_customer_map

    return parse_store_customer_map(settings.store_customer_map)


def _load_cursor() -> str | None:
    return frappe.cache().get_value("rt_posting_cursor")


def _save_cursor(cursor: str) -> None:
    frappe.cache().set_value("rt_posting_cursor", cursor)


def _safe(message: str) -> str:
    from .reasons import scrub_message

    return scrub_message(message)
