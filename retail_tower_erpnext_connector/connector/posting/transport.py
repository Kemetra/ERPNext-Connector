# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Pull/ack transport for the 012 posting feed (T011).

The connector authenticates *to* DP2 (it is the client; DP2 makes no outbound calls —
spec 003 / Gate G4) and uses the fixed two-operation surface:
  - ``connectorPullPostings`` (GET, cursor-paged) — pull pending work-items;
  - ``connectorAckOutcome``   (POST) — ack a typed outcome for one work-item.

The live HTTP mechanism is abstracted behind :class:`HttpTransport` (a Protocol — the
repo's Repository pattern). The client logic is unit-tested here against a fake; the
concrete HTTP/auth-backed transport and the live round-trip are ⏳ BENCH-VALIDATION
(standing-rules §6). This module imports NO frappe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import MissingErpnextItemRef, OutcomeAckRequest, PostingWorkItem

# spec-003 substrate: the DP2 request_id correlation travels on every call (Principle V).
CORRELATION_HEADER = "X-Request-Id"
# 012 connectorAckOutcome is x-idempotency: required.
IDEMPOTENCY_HEADER = "Idempotency-Key"

_PULL_PATH = "/connector/postings"
_ACK_PATH_TEMPLATE = "/connector/postings/{work_item_ref}/outcome"


class HttpTransport(Protocol):
    """The minimal HTTP surface the client needs. Implemented by a real auth-backed
    client in the deferred bench glue, and by a fake in unit tests."""

    def get(self, path: str, *, params: dict, headers: dict) -> dict: ...

    def post(self, path: str, *, json: dict, headers: dict) -> dict: ...


@dataclass(frozen=True)
class PostingFeedPage:
    """A parsed page of the 012 posting feed (mirrors ``PostingFeedPage``)."""

    items: tuple[PostingWorkItem, ...]
    cursor: str
    next_page_token: str | None


@dataclass(frozen=True)
class InvalidItem:
    """A raw feed item that failed to parse — isolated, not aborted (re-P2b).

    ``work_item_ref`` is read directly off the raw item (so the bad item can still be acked
    by ref even though it never became a :class:`PostingWorkItem`). ``error_kind`` classifies
    the violation for the rejection reason.
    """

    work_item_ref: str
    error_kind: str
    message: str
    raw: dict


@dataclass(frozen=True)
class RawFeedPage:
    """A page split into successfully-parsed items and isolated invalid ones (re-P2b).

    The page is NEVER aborted on a bad line: valid items parse and post, invalid items are
    surfaced for per-item rejection, and the caller raises a page-degraded alert AFTER
    recording every per-item outcome.
    """

    items: tuple[PostingWorkItem, ...]
    invalid: tuple[InvalidItem, ...]
    cursor: str
    next_page_token: str | None


class PostingFeedClient:
    """Consumes the fixed 012 pull/ack surface over an injected :class:`HttpTransport`."""

    def __init__(self, transport: HttpTransport, *, correlation_id: str) -> None:
        self._transport = transport
        self._correlation_id = correlation_id

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {CORRELATION_HEADER: self._correlation_id}
        if extra:
            headers.update(extra)
        return headers

    def pull_postings(self, *, since: str | None) -> PostingFeedPage:
        """``connectorPullPostings`` — pull a cursor-ordered page of pending work-items.

        An empty page is a valid, non-error result (no pending postings).
        """
        params: dict = {}
        if since is not None:
            params["since"] = since
        raw = self._transport.get(_PULL_PATH, params=params, headers=self._headers())
        items = tuple(PostingWorkItem.from_wire(item) for item in raw.get("items", []))
        # 012 PostingFeedPage.cursor is required, minLength 1. An absent/empty cursor is an
        # upstream contract violation — raise rather than substitute "" (which would silently
        # re-baseline the next pull instead of advancing). F-011.
        cursor = raw.get("cursor")
        if not cursor:
            raise ValueError("posting feed page missing required non-empty cursor (012)")
        return PostingFeedPage(
            items=items,
            cursor=str(cursor),
            next_page_token=(
                None if raw.get("next_page_token") is None else str(raw["next_page_token"])
            ),
        )

    def pull_postings_raw(self, *, since: str | None) -> RawFeedPage:
        """``connectorPullPostings`` — pull a page, isolating unparseable items (re-P2b).

        Unlike :meth:`pull_postings` (which aborts the whole page on a bad line), this parses
        each item independently: a line missing ``erpnextItemRef`` (or any parse failure) becomes
        an :class:`InvalidItem` rather than aborting valid siblings. The caller acks each invalid
        item ``permanently_rejected``/``validation`` and raises a page-degraded alert AFTER.
        """
        params: dict = {}
        if since is not None:
            params["since"] = since
        raw = self._transport.get(_PULL_PATH, params=params, headers=self._headers())

        items: list[PostingWorkItem] = []
        invalid: list[InvalidItem] = []
        for entry in raw.get("items", []):
            try:
                items.append(PostingWorkItem.from_wire(entry))
            except MissingErpnextItemRef as exc:
                invalid.append(
                    InvalidItem(
                        work_item_ref=str(entry.get("workItemRef", "")),
                        error_kind="missing_erpnext_item_ref",
                        message=str(exc),
                        raw=entry,
                    )
                )
            except (ValueError, KeyError, TypeError) as exc:
                # Any other malformed item is also isolated, not page-aborting (re-P2b).
                invalid.append(
                    InvalidItem(
                        work_item_ref=str(entry.get("workItemRef", "")),
                        error_kind="malformed_work_item",
                        message=str(exc),
                        raw=entry,
                    )
                )

        cursor = raw.get("cursor")
        if not cursor:
            raise ValueError("posting feed page missing required non-empty cursor (012)")
        return RawFeedPage(
            items=tuple(items),
            invalid=tuple(invalid),
            cursor=str(cursor),
            next_page_token=(
                None if raw.get("next_page_token") is None else str(raw["next_page_token"])
            ),
        )

    def ack_outcome(
        self,
        work_item_ref: str,
        ack: OutcomeAckRequest,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        """``connectorAckOutcome`` — POST the typed outcome for one work-item.

        Posts ONLY the outcome; never mutates the DP2 sale fact (012 O-3 / Principle IV).
        """
        extra = {IDEMPOTENCY_HEADER: idempotency_key} if idempotency_key else None
        return self._transport.post(
            _ACK_PATH_TEMPLATE.format(work_item_ref=work_item_ref),
            json=ack.to_wire(),
            headers=self._headers(extra),
        )
