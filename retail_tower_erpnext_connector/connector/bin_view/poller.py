# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Bin-view poller — the scheduled entrypoint — BENCH-VALIDATION.

Registered as a ``scheduler_events`` cron in ``hooks.py`` (Frappe v15 runs it on the DEFAULT
queue, 300 s job timeout). On each tick it:

  1. builds the 019 client over the spec-003 auth (reuses Connector Settings
     ``dp2_base_url`` + ``dp2_token``) + the frappe-backed Bin reader + a UTC clock;
  2. folds in the outcomes that finished paged-report jobs left behind (see below);
  3. drains the bounded retry set (RT-176, :mod:`.retry`), oldest first: a v1 request is
     re-attempted inline (at most ``retry.MAX_RETRIES_PER_TICK`` per tick, each charged and
     checkpointed before it runs and checkpointed again after it); a paged request is handed
     off to a long-queue job (cheap — no network);
  4. pulls wanted Bin-view reads (``binViewPullRequests``) page by page; v1 requests are read
     and reported inline (one report, v1 key), paged requests (``maxWindows > 1``) are handed
     off.

PAGED REPORTS RUN OFF THE CRON QUEUE (Codex P1s on #56). One paged attempt makes one DP2 call
per window (up to ``maxWindows``, 30 s transport timeout each), which can outlast the cron's
300 s default-queue timeout; a killed worker would restart the attempt at window 0 forever.
So the tick hands each paged request to :func:`run_paged_report_job` via
``frappe.enqueue(queue="long", timeout=<budget + margin>, job_id="rt_bin_view_paged::<ref>",
deduplicate=True)``: one job per request at a time, with an explicit timeout derived from
``worker.attempt_budget_s(maxWindows)`` (``maxWindows x 30 s + 60 s``, capped at 1200 s) plus
:data:`_JOB_TIMEOUT_MARGIN_S`, so always under the long queue's 1500 s. Inside the job an
:class:`~.worker.AttemptDeadline` (same budget) ends the attempt cleanly BEFORE any window call
that could overrun it — no ``isFinal`` is sent and the job is never killed mid-write. The
handed-off request is charged in the retry set BEFORE the enqueue; the job writes its outcome
to ``rt_bin_view_outcome::<ref>`` and the next tick folds it in (resolve, or settle the
failure). The retry set therefore has ONE writer — the cron tick, which Frappe never runs
twice at once — and a job that dies without an outcome simply counts as a failed attempt.
An attempt is never resumed across jobs/ticks: stock-view 1.2 defines no attempt lifetime or
continuation, only that window 0 under a new ``attemptRef`` supersedes, so every retry is a
fresh attempt.

A request whose report did not reach completion for a RETRYABLE reason (a transport error,
an unexpected DP2 status, a mid-attempt failure, a superseded attempt, an explicit
``complete: false``, the attempt deadline) stays in the retry set, which is saved BEFORE the
cursor advances past its page — so a failed run is never stranded behind the saved cursor (the
pre-RT-176 defect). After ``retry.MAX_RETRY_TICKS`` failed retries it is abandoned with
``bin_view.report.incomplete_abandoned``. Deterministic refusals are terminal and logged, not
retried: the v1 overflow, the paged ``bin_view.window.limit_exceeded``, a 409 idempotency-key
conflict, and a 404 stale run.

This is the composition root; it imports ``frappe`` and the glue, so it is validated on
a bench, not locally (standing-rules §6). The pure pull/report/quantize/retry logic lives in
``transport.py`` + ``worker.py`` + ``retry.py`` (unit-tested locally); this is the thin frappe
shell (its tick and job logic is also exercised locally against a frappe stand-in).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import frappe

from ..request_id import new_request_id
from . import worker
from .contracts import BinViewRequest
from .retry import ABANDONED, MAX_RETRIES_PER_TICK, RetrySet
from .transport import BinViewClient, ReportConflict, ReportNotFound, WindowSequenceConflict
from .worker import (
    AttemptDeadline,
    AttemptDeadlineExceeded,
    ReportIncomplete,
    WindowLimitExceeded,
    WindowOverflowError,
)

_LOGGER = "retail_tower_bin_view"
# Bounded pages per tick — the scheduler re-enters next cron; the report is idempotent
# (a re-report of the same request replays), so a mid-loop interruption is safe.
_MAX_PAGES_PER_TICK = 20
_CURSOR_KEY = "rt_bin_view_cursor"
_RETRY_KEY = "rt_bin_view_retry"
_OUTCOME_KEY_PREFIX = "rt_bin_view_outcome::"
_OUTCOME_TTL_S = 24 * 3600
_JOB_ID_PREFIX = "rt_bin_view_paged::"
_JOB_METHOD = "retail_tower_erpnext_connector.connector.bin_view.poller.run_paged_report_job"
_JOB_QUEUE = "long"
# Head-room between the in-job attempt deadline and the RQ job timeout (Bin read + job setup).
_JOB_TIMEOUT_MARGIN_S = 120
# The attempt deadline's clock (a module attribute so tests can drive it deterministically).
_monotonic = time.monotonic


@dataclass(frozen=True)
class _Outcome:
    """How one read-and-report attempt ended: ``resolved`` (complete or terminal) or not."""

    resolved: bool
    reason: str = ""
    detail: str = ""


def run_bin_view_poll() -> None:
    """Scheduler entrypoint — fold job outcomes, drain retries, pull + report one batch."""
    try:
        client, reader, clock = _build_bin_view_path()
    except Exception as exc:  # config/auth not ready — log + skip the tick (no partial work).
        frappe.logger(_LOGGER).warning(
            {"event": "bin_view.poll.skipped", "reason": _safe(str(exc))}
        )
        return

    retries = RetrySet(_load_retry_state())
    _fold_job_outcomes(retries)
    _save_retry_state(retries)
    attempted = _drain_retries(retries, client=client, reader=reader, clock=clock)

    since: str | None = _load_cursor()
    pages = 0
    while pages < _MAX_PAGES_PER_TICK:
        page = client.pull_requests(since=since)
        for request in page.items:
            if request.request_ref in attempted:
                continue  # already handled this tick (a re-baselined feed can re-offer it)
            attempted.add(request.request_ref)
            _handle_feed_request(request, client=client, reader=reader, clock=clock,
                                 retries=retries)
        pages += 1
        # Retry state FIRST: a request that failed on this page must be durable before the
        # cursor moves past it, or its run is stranded (pre-RT-176 defect).
        _save_retry_state(retries)
        _save_cursor(page.cursor)
        since = page.cursor
        if page.next_page_token is None:
            break  # caught up — no more wanted reads


def _drain_retries(retries: RetrySet, *, client, reader, clock) -> set[str]:
    """Hand off every paged retry; re-attempt at most ``MAX_RETRIES_PER_TICK`` v1 retries inline.

    Returns the request refs handled this tick (so a re-offer from the feed is skipped).
    """
    attempted: set[str] = set()
    inline_budget = MAX_RETRIES_PER_TICK
    for request in retries.pending():
        if request.item_window.is_paged:
            attempted.add(request.request_ref)
            _hand_off(request, retries)
        elif inline_budget > 0:
            inline_budget -= 1
            attempted.add(request.request_ref)
            _retry_inline(request, client=client, reader=reader, clock=clock, retries=retries)
    return attempted


def run_paged_report_job(request_wire: dict) -> None:
    """Long-queue job: ONE paged read-and-report attempt under an explicit time budget.

    Never touches the retry set (the cron tick is its only writer); it leaves its outcome under
    ``rt_bin_view_outcome::<ref>`` for the next tick to fold in. If the job dies before writing
    one, the next tick sees no outcome and no job in flight, and counts the charged attempt as
    failed.
    """
    request = BinViewRequest.from_wire(request_wire)
    try:
        client, reader, clock = _build_bin_view_path()
    except Exception as exc:
        frappe.logger(_LOGGER).warning(
            {"event": "bin_view.poll.skipped", "reason": _safe(str(exc)),
             "request_ref": request.request_ref}
        )
        return
    deadline = AttemptDeadline(
        worker.attempt_budget_s(request.item_window.max_windows or 1), monotonic=_monotonic
    )
    outcome = _attempt(request, client=client, reader=reader, clock=clock, deadline=deadline)
    frappe.cache().set_value(
        _OUTCOME_KEY_PREFIX + request.request_ref,
        {"resolved": outcome.resolved, "reason": outcome.reason, "detail": outcome.detail},
        expires_in_sec=_OUTCOME_TTL_S,
    )


def _handle_feed_request(request, *, client, reader, clock, retries: RetrySet) -> None:
    if request.item_window.is_paged:
        _hand_off(request, retries)
        return
    outcome = _attempt(request, client=client, reader=reader, clock=clock)
    if outcome.resolved:
        retries.resolve(request.request_ref)
    else:
        _log_failure(request, retries.record_failure(request), outcome)


def _retry_inline(request, *, client, reader, clock, retries: RetrySet) -> None:
    """Re-attempt one v1 retry-set request: charge it, checkpoint, attempt, checkpoint again.

    The checkpoint BEFORE the attempt persists the charge (and the rotation to the back), so a
    worker killed mid-attempt still counts the attempt and the next tick starts with the
    requests behind it. The checkpoint AFTER persists the outcome (resolved or still queued).
    """
    if not _charge(request, retries):
        return
    outcome = _attempt(request, client=client, reader=reader, clock=clock)
    _settle(request, retries, outcome)
    _save_retry_state(retries)


def _hand_off(request, retries: RetrySet) -> None:
    """Charge a paged request, checkpoint, then enqueue its attempt on the long queue.

    Skipped (not charged) while that request's job is still queued or running.
    """
    job_id = _JOB_ID_PREFIX + request.request_ref
    if _job_in_flight(job_id):
        return
    if not _charge(request, retries):
        return
    budget = worker.attempt_budget_s(request.item_window.max_windows or 1)
    try:
        frappe.enqueue(
            _JOB_METHOD,
            queue=_JOB_QUEUE,
            timeout=budget + _JOB_TIMEOUT_MARGIN_S,
            job_id=job_id,
            deduplicate=True,
            request_wire=request.to_wire(),
        )
    except Exception as exc:  # Redis/queue unavailable — already charged; the next tick retries.
        frappe.logger(_LOGGER).warning(
            {"event": "bin_view.report.enqueue_failed", "request_ref": request.request_ref,
             "detail": _safe(str(exc))}
        )


def _charge(request, retries: RetrySet) -> bool:
    """Count one attempt up front (rotating it to the back) and checkpoint; False = abandoned.

    A request already held is charged as a retry; a new one (from the feed) is recorded, which
    also applies the ``MAX_PENDING`` bound.
    """
    held = request.request_ref in retries
    charged = retries.charge_retry(request) if held else retries.record_failure(request)
    _save_retry_state(retries)
    if charged.status == ABANDONED:
        # A held request: its previous charged attempt was the last one allowed (it never
        # settled). A new one: the retry set is full.
        reason = "retry_budget_spent" if held else "retry_set_full"
        _log_failure(request, charged, _Outcome(False, reason))
        return False
    return True


def _settle(request, retries: RetrySet, outcome: _Outcome) -> None:
    if outcome.resolved:
        retries.resolve(request.request_ref)
    else:
        _log_failure(request, retries.settle_failed_retry(request), outcome)


def _fold_job_outcomes(retries: RetrySet) -> None:
    """Apply the outcomes finished paged-report jobs left for requests still in the retry set."""
    cache = frappe.cache()
    for request in retries.pending():
        key = _OUTCOME_KEY_PREFIX + request.request_ref
        raw = cache.get_value(key)
        if not isinstance(raw, dict):
            continue
        cache.delete_value(key)
        outcome = _Outcome(bool(raw.get("resolved")), str(raw.get("reason") or ""),
                           str(raw.get("detail") or ""))
        _settle(request, retries, outcome)


def _attempt(request, *, client, reader, clock, deadline=None) -> _Outcome:
    """One read-and-report attempt for ``request``; classifies how it ended.

    Never raises an ``Exception``: completion and the terminal refusals are ``resolved`` (and
    logged); retryable failures come back unresolved with a reason for the caller to record.
    """
    ref = request.request_ref
    log = frappe.logger(_LOGGER)
    try:
        worker.process_request(request, client=client, reader=reader, clock=clock,
                               deadline=deadline)
    except WindowSequenceConflict as exc:
        if exc.window_seq != 0:
            # This attempt was superseded / went stale mid-sequence — retry with a fresh one.
            return _Outcome(False, "window_sequence_conflict", _safe(str(exc)))
        # Window 0 of a NEW attempt is refused only once another attempt of this request is
        # already complete (stock-view 1.2) — the run has its report; nothing to retry.
        log.info({"event": "bin_view.report.already_complete", "request_ref": ref,
                  "detail": _safe(str(exc))})
    except ReportConflict as exc:
        # Same key + a different snapshot — operator attention; never blind-retry.
        log.error({"event": "bin_view.report.conflict", "request_ref": ref,
                   "detail": _safe(str(exc))})
    except ReportNotFound as exc:
        # The run completed / went away between pull and report (non-disclosing).
        log.info({"event": "bin_view.report.stale", "request_ref": ref, "detail": _safe(str(exc))})
    except WindowOverflowError as exc:
        # v1 request: the warehouse exceeds the single window — REFUSE to report a
        # known-incomplete snapshot (no silent truncation). Deterministic: not retried.
        log.error({"event": "bin_view.window.overflow", "request_ref": ref,
                   "warehouse": request.erpnext_warehouse_ref, "detail": _safe(str(exc))})
    except WindowLimitExceeded as exc:
        # Paged request: more than maxWindows x maxItems items — nothing was reported.
        log.error({"event": "bin_view.window.limit_exceeded", "request_ref": ref,
                   "warehouse": request.erpnext_warehouse_ref, "limit": exc.limit,
                   "detail": _safe(str(exc))})
    except (AttemptDeadlineExceeded, ReportIncomplete) as exc:
        return _incomplete_attempt(ref, exc)
    except Exception as exc:  # transport / unexpected DP2 status / read failure — retryable.
        return _Outcome(False, type(exc).__name__, _safe(str(exc)))
    return _Outcome(True)


def _incomplete_attempt(ref: str, exc: Exception) -> _Outcome:
    """A paged attempt that ended without completing the report — retryable."""
    if isinstance(exc, AttemptDeadlineExceeded):
        # Ended cleanly before a window that could overrun the budget (no isFinal sent).
        frappe.logger(_LOGGER).warning(
            {"event": "bin_view.report.deadline_reached", "request_ref": ref,
             "window_seq": exc.window_seq, "detail": _safe(str(exc))}
        )
        return _Outcome(False, "attempt_deadline", _safe(str(exc)))
    return _Outcome(False, "report_incomplete", _safe(str(exc)))


def _log_failure(request, failure, outcome: _Outcome) -> None:
    record = {
        "request_ref": request.request_ref,
        "warehouse": request.erpnext_warehouse_ref,
        "failures": failure.failures,
        "reason": outcome.reason,
        "detail": outcome.detail,
    }
    if failure.status == ABANDONED:
        frappe.logger(_LOGGER).error({"event": "bin_view.report.incomplete_abandoned", **record})
    else:
        frappe.logger(_LOGGER).warning({"event": "bin_view.report.retry_scheduled", **record})


def _job_in_flight(job_id: str) -> bool:
    """True while the paged-report job ``job_id`` is queued or started (Frappe v15 RQ)."""
    from frappe.utils.background_jobs import is_job_enqueued

    return bool(is_job_enqueued(job_id))


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
