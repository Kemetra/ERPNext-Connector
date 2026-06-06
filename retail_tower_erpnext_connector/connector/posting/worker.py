# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Posting page processor — the re-P2b hybrid isolate + raise-after loop (Task A).

Per the ratified re-P2b decision: a feed page line missing ``erpnextItemRef`` is an upstream
DP2 contract violation (rider R2). The connector:

  - treats it as a **terminal validation rejection for that work item only**
    (`permanently_rejected` / `validation` — the wire category is the closed-set `validation`;
    the specificity rides in the reason ``message``);
  - **never** resolves, searches, creates, or substitutes an ERPNext Item;
  - **continues** processing the valid work items on the same page;
  - records every per-item outcome FIRST, then **raises a page-degraded alert AFTER** so the DP2
    feed contract can be fixed — never an abort that strands valid or already-acked items;
  - relies on the per-outcome ack key + the idempotency store to make a scheduler retry safe.

This module imports NO frappe — it is pure orchestration over the injected client + poster.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import OutcomeAckRequest, RejectionReason
from .transport import PostingFeedClient

# Operational: a page that processed but contained ≥1 contract-violating item. Raised AFTER all
# per-item outcomes are acked, so it signals "feed is degraded, fix upstream" without losing work.
_MISSING_REF_MESSAGE = (
    "feed page contained {n} line(s) missing erpnextItemRef (upstream DP2 contract violation, "
    "rider R2) — rejected per-item: {refs}"
)


class PageDegraded(Exception):
    """Operational-alert type for a degraded page (carried ≥1 contract-violating item).

    NOT raised by :func:`process_page` — that returns a ``PageResult`` with ``degraded=True`` and
    advances the cursor (every item reached a terminal outcome; re-pulling is the forbidden retry).
    This type exists so the caller can surface the breach (log/alert) with a typed payload.
    """


@dataclass(frozen=True)
class PageResult:
    """Outcome of processing one pull page.

    ``degraded`` is True when the page carried ≥1 contract-violating item (all of which were acked
    `permanently_rejected` before this result was returned). The cursor still advances on a degraded
    page — every item reached a terminal outcome, so re-pulling would be a forbidden retry (re-P2b).
    ``degraded_message`` is the operational-alert text the caller logs (None when not degraded).
    """

    cursor: str
    next_page_token: str | None
    posted_count: int
    rejected_refs: tuple[str, ...]
    degraded: bool
    degraded_message: str | None = None


def process_page(
    client: PostingFeedClient,
    ack_client,
    *,
    since: str | None,
    post_valid,
) -> PageResult:
    """Process one pull page with re-P2b isolation.

    ``client.pull_postings_raw`` splits the page into valid items + isolated invalid ones.
    ``post_valid(work_item)`` posts a valid item (the caller injects the real posting path —
    e.g. ``frappe_glue.post_work_item`` bound with its deps, or a fake in tests). ``ack_client``
    acks the invalid items (same interface as :class:`PostingFeedClient`).

    Returns a :class:`PageResult`; raises :class:`PageDegraded` AFTER recording all outcomes if
    the page carried any invalid item.
    """
    page = client.pull_postings_raw(since=since)

    # 1. Post every valid work item (the happy path; each is independently idempotent).
    for work_item in page.items:
        post_valid(work_item)

    # 2. Ack each invalid item as a terminal per-item rejection — no substitution, no resolution.
    rejected_refs: list[str] = []
    for bad in page.invalid:
        reason = RejectionReason(
            category="validation",  # closed 012 set; no `missing_erpnext_item_ref` wire category
            message=f"{bad.error_kind}: {bad.message}",
        )
        ack_client.ack_outcome(
            bad.work_item_ref,
            OutcomeAckRequest.permanently_rejected(reason),
            idempotency_key=f"{bad.work_item_ref}:permanently_rejected",
        )
        rejected_refs.append(bad.work_item_ref)

    # 3. Return a result carrying `degraded` + the advanced cursor. We do NOT raise: every item
    #    on the page reached a terminal outcome (posted or acked-rejected), so the cursor MUST
    #    advance — re-pulling would be the forbidden page-level retry of already-acked items
    #    (re-P2b: "no page-level retry... emits an operational alert"). The caller logs the alert
    #    and advances. ``degraded_message`` is the alert text when degraded.
    return PageResult(
        cursor=page.cursor,
        next_page_token=page.next_page_token,
        posted_count=len(page.items),
        rejected_refs=tuple(rejected_refs),
        degraded=bool(page.invalid),
        degraded_message=(
            _MISSING_REF_MESSAGE.format(n=len(rejected_refs), refs=", ".join(rejected_refs))
            if page.invalid
            else None
        ),
    )
