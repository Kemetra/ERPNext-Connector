# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Bin-view poller — the scheduled entrypoint — BENCH-VALIDATION.

Registered as a ``scheduler_events`` cron in ``hooks.py``. On each tick it:

  1. builds the 019 client over the spec-003 auth (reuses Connector Settings
     ``dp2_base_url`` + ``dp2_token``) + the frappe-backed Bin reader + a UTC clock;
  2. re-attempts every request in the bounded retry set (RT-176, :mod:`.retry`) — each a
     FRESH read attempt (a paged request gets a new ``attemptRef`` from window 0);
  3. pulls wanted Bin-view reads (``binViewPullRequests``) page by page;
  4. for each request, reads the live ERPNext ``Bin`` for the warehouse and reports the
     snapshot (``binViewReportSnapshot``) — one report (v1) or windows 0..N (stock-view 1.2,
     ``maxWindows > 1``) — with deterministic Idempotency-Keys.

A request whose report did not reach completion for a RETRYABLE reason (a transport error,
an unexpected DP2 status, a mid-attempt failure, a superseded attempt, an explicit
``complete: false``) is put in the retry set, which is saved BEFORE the cursor advances past
its page — so a failed run is never stranded behind the saved cursor (the pre-RT-176 defect).
After ``retry.MAX_RETRY_TICKS`` failed retries it is abandoned with
``bin_view.report.incomplete_abandoned``. Deterministic refusals are terminal and logged, not
retried: the v1 overflow, the paged ``bin_view.window.limit_exceeded``, a 409 idempotency-key
conflict, and a 404 stale run.

This is the composition root; it imports ``frappe`` and the glue, so it is validated on
a bench, not locally (standing-rules §6). The pure pull/report/quantize/retry logic lives in
``transport.py`` + ``worker.py`` + ``retry.py`` (unit-tested locally); this is the thin frappe
shell (its tick logic is also exercised locally against a frappe stand-in).
"""

from __future__ import annotations

import frappe

from ..request_id import new_request_id
from . import worker
from .retry import ABANDONED, RetrySet
from .transport import BinViewClient, ReportConflict, ReportNotFound, WindowSequenceConflict
from .worker import ReportIncomplete, WindowLimitExceeded, WindowOverflowError

_LOGGER = "retail_tower_bin_view"
# Bounded pages per tick — the scheduler re-enters next cron; the report is idempotent
# (a re-report of the same request replays), so a mid-loop interruption is safe.
_MAX_PAGES_PER_TICK = 20
_CURSOR_KEY = "rt_bin_view_cursor"
_RETRY_KEY = "rt_bin_view_retry"


def run_bin_view_poll() -> None:
    """Scheduler entrypoint — retry + pull + read-Bin + report one batch of bin-view requests."""
    try:
        client, reader, clock = _build_bin_view_path()
    except Exception as exc:  # config/auth not ready — log + skip the tick (no partial work).
        frappe.logger(_LOGGER).warning(
            {"event": "bin_view.poll.skipped", "reason": _safe(str(exc))}
        )
        return

    retries = RetrySet(_load_retry_state())
    attempted: set[str] = set()
    for request in retries.pending():
        attempted.add(request.request_ref)
        _attempt(request, client=client, reader=reader, clock=clock, retries=retries)
    _save_retry_state(retries)

    since: str | None = _load_cursor()
    pages = 0
    while pages < _MAX_PAGES_PER_TICK:
        page = client.pull_requests(since=since)
        for request in page.items:
            if request.request_ref in attempted:
                continue  # already re-attempted this tick (a re-baselined feed can re-offer it)
            attempted.add(request.request_ref)
            _attempt(request, client=client, reader=reader, clock=clock, retries=retries)
        pages += 1
        # Retry state FIRST: a request that failed on this page must be durable before the
        # cursor moves past it, or its run is stranded (pre-RT-176 defect).
        _save_retry_state(retries)
        _save_cursor(page.cursor)
        since = page.cursor
        if page.next_page_token is None:
            break  # caught up — no more wanted reads


def _attempt(request, *, client, reader, clock, retries: RetrySet) -> None:
    """One read-and-report attempt for ``request``; classifies the outcome for the retry set.

    Never raises: every outcome is either resolved (completed / terminal, logged) or recorded
    as a failure (retried on a later tick, or abandoned once the bound is reached).
    """
    ref = request.request_ref
    log = frappe.logger(_LOGGER)
    try:
        worker.process_request(request, client=client, reader=reader, clock=clock)
    except WindowSequenceConflict as exc:
        if exc.window_seq == 0:
            # Window 0 of a NEW attempt is refused only once another attempt of this request
            # is already complete (stock-view 1.2) — the run has its report; nothing to retry.
            retries.resolve(ref)
            log.info(
                {"event": "bin_view.report.already_complete", "request_ref": ref,
                 "detail": _safe(str(exc))}
            )
        else:
            # This attempt was superseded / went stale mid-sequence — retry with a fresh one.
            _record_failure(request, retries, reason="window_sequence_conflict",
                            detail=str(exc))
    except ReportConflict as exc:
        # Same key + a different snapshot — operator attention; never blind-retry.
        retries.resolve(ref)
        log.error(
            {"event": "bin_view.report.conflict", "request_ref": ref, "detail": _safe(str(exc))}
        )
    except ReportNotFound as exc:
        # The run completed / went away between pull and report (non-disclosing).
        retries.resolve(ref)
        log.info({"event": "bin_view.report.stale", "request_ref": ref, "detail": _safe(str(exc))})
    except WindowOverflowError as exc:
        # v1 request: the warehouse exceeds the single window — REFUSE to report a
        # known-incomplete snapshot (no silent truncation). Deterministic: not retried.
        retries.resolve(ref)
        log.error(
            {"event": "bin_view.window.overflow", "request_ref": ref,
             "warehouse": request.erpnext_warehouse_ref, "detail": _safe(str(exc))}
        )
    except WindowLimitExceeded as exc:
        # Paged request: more than maxWindows x maxItems items — nothing was reported.
        retries.resolve(ref)
        log.error(
            {"event": "bin_view.window.limit_exceeded", "request_ref": ref,
             "warehouse": request.erpnext_warehouse_ref, "limit": exc.limit,
             "detail": _safe(str(exc))}
        )
    except ReportIncomplete as exc:
        _record_failure(request, retries, reason="report_incomplete", detail=str(exc))
    except Exception as exc:  # transport / unexpected DP2 status / read failure — retryable.
        _record_failure(request, retries, reason=type(exc).__name__, detail=str(exc))
    else:
        retries.resolve(ref)


def _record_failure(request, retries: RetrySet, *, reason: str, detail: str) -> None:
    outcome = retries.record_failure(request)
    record = {
        "request_ref": request.request_ref,
        "warehouse": request.erpnext_warehouse_ref,
        "failures": outcome.failures,
        "reason": reason,
        "detail": _safe(detail),
    }
    if outcome.status == ABANDONED:
        frappe.logger(_LOGGER).error({"event": "bin_view.report.incomplete_abandoned", **record})
    else:
        frappe.logger(_LOGGER).warning({"event": "bin_view.report.retry_scheduled", **record})


def _build_bin_view_path():
    """Construct the 019 client + the frappe-backed Bin reader + a UTC clock.

    Reuses the Connector Settings ``dp2_base_url`` + ``dp2_token`` (the posting poller's
    transport pattern). Raises if base-URL/token unset → the tick skips cleanly.
    """
    from .frappe_glue import FrappeBinReader, UtcClock
    from ..posting.poller import _build_http_transport  # reuse the auth-backed transport

    # RT-39 — a UUID so Backend-Core keeps + echoes it (it re-mints any non-UUID X-Request-Id).
    correlation_id = new_request_id()
    settings = frappe.get_doc("Connector Settings")
    transport = _build_http_transport(settings)
    client = BinViewClient(transport, correlation_id=correlation_id)
    return client, FrappeBinReader(), UtcClock()


def _load_cursor() -> str | None:
    return frappe.cache().get_value(_CURSOR_KEY)


def _save_cursor(cursor: str) -> None:
    frappe.cache().set_value(_CURSOR_KEY, cursor)


def _load_retry_state():
    return frappe.cache().get_value(_RETRY_KEY)


def _save_retry_state(retries: RetrySet) -> None:
    frappe.cache().set_value(_RETRY_KEY, retries.to_state())


def _safe(message: str) -> str:
    from ..posting.reasons import scrub_message

    return scrub_message(message)
