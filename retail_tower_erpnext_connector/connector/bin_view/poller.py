# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Bin-view poller — the scheduled entrypoint — BENCH-VALIDATION.

Registered as a ``scheduler_events`` cron in ``hooks.py``. On each tick it:

  1. builds the 019 client over the spec-003 auth (reuses Connector Settings
     ``dp2_base_url`` + ``dp2_token``) + the frappe-backed Bin reader + a UTC clock;
  2. pulls wanted Bin-view reads (``binViewPullRequests``) page by page;
  3. for each request, reads the live ERPNext ``Bin`` for the warehouse and reports the
     snapshot (``binViewReportSnapshot``) with a deterministic Idempotency-Key.

This is the composition root; it imports ``frappe`` and the glue, so it is validated on
a bench, not locally (standing-rules §6). The pure pull/report/quantize logic lives in
``transport.py`` + ``worker.py`` (unit-tested locally); this is the thin frappe shell.
"""

from __future__ import annotations

import frappe

from . import worker
from .transport import BinViewClient, ReportConflict, ReportNotFound

_LOGGER = "retail_tower_bin_view"
# Bounded pages per tick — the scheduler re-enters next cron; the report is idempotent
# (a re-report of the same request replays), so a mid-loop interruption is safe.
_MAX_PAGES_PER_TICK = 20


def run_bin_view_poll() -> None:
    """Scheduler entrypoint — pull + read-Bin + report one batch of bin-view requests."""
    try:
        client, reader, clock = _build_bin_view_path()
    except Exception as exc:  # config/auth not ready — log + skip the tick (no partial work).
        frappe.logger(_LOGGER).warning(
            {"event": "bin_view.poll.skipped", "reason": _safe(str(exc))}
        )
        return

    since: str | None = _load_cursor()
    pages = 0
    while pages < _MAX_PAGES_PER_TICK:
        page = client.pull_requests(since=since)
        for request in page.items:
            try:
                worker.process_request(request, client=client, reader=reader, clock=clock)
            except ReportConflict as exc:
                # Same key + a different snapshot — operator attention; never blind-retry.
                frappe.logger(_LOGGER).error(
                    {"event": "bin_view.report.conflict", "request_ref": request.request_ref,
                     "detail": _safe(str(exc))}
                )
            except ReportNotFound as exc:
                # The run completed / went away between pull and report (non-disclosing).
                frappe.logger(_LOGGER).info(
                    {"event": "bin_view.report.stale", "request_ref": request.request_ref,
                     "detail": _safe(str(exc))}
                )
        pages += 1
        _save_cursor(page.cursor)
        since = page.cursor
        if page.next_page_token is None:
            break  # caught up — no more wanted reads


def _build_bin_view_path():
    """Construct the 019 client + the frappe-backed Bin reader + a UTC clock.

    Reuses the Connector Settings ``dp2_base_url`` + ``dp2_token`` (the posting poller's
    transport pattern). Raises if base-URL/token unset → the tick skips cleanly.
    """
    from .frappe_glue import FrappeBinReader, UtcClock
    from ..posting.poller import _build_http_transport  # reuse the auth-backed transport

    correlation_id = frappe.generate_hash(length=16)
    settings = frappe.get_doc("Connector Settings")
    transport = _build_http_transport(settings)
    client = BinViewClient(transport, correlation_id=correlation_id)
    return client, FrappeBinReader(), UtcClock()


def _load_cursor() -> str | None:
    return frappe.cache().get_value("rt_bin_view_cursor")


def _save_cursor(cursor: str) -> None:
    frappe.cache().set_value("rt_bin_view_cursor", cursor)


def _safe(message: str) -> str:
    from ..posting.reasons import scrub_message

    return scrub_message(message)
