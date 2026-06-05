# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Frappe-coupled posting glue — ⏳ BENCH-VALIDATION (T031/T032/T041/T051/T090).

This is the ONLY posting module that imports ``frappe``. It composes the pure-Python core
(contracts / transport / builder / idempotency / reasons / uom) into the live posting flow
against an ERPNext site:

  - T031 — submit the built Sales Invoice on ERPNext (interim SI-only; rider R1).
  - T032 — ack ``posted`` + ``documentRef`` over ``connectorAckOutcome``.
  - T041 — duplicate ``posted`` echoes the existing ``documentRef`` (no second document).
  - T051 — transient → ``failed_transient``; non-retryable → ``permanently_rejected`` + reason.
  - T090 — structured logs + signals carrying the DP2 ``request_id`` correlation; no secrets.

⚠️ NOT RUN AND NOT CLAIMED PASSING IN THIS LANE. This machine has no Frappe bench
(standing-rules §6); these paths are validated on a staging ERPNext v15 site. The frappe
import below intentionally fails at local import time — that is expected and is why this
module is isolated from the locally-tested core.

This module does NOT register any hook (FR-014 — ``hooks.py`` stays empty; the poller
``scheduler_event`` is the deferred [GATED] T093) and does NOT define a DocType (the
idempotency-store DocType is the deferred [GATED] T020). It RECEIVES an
:class:`IdempotencyStore` adapter; it does not create one.
"""

from __future__ import annotations

import frappe

from .builder import UnmappedUnit, build_sales_invoice
from .contracts import ErpnextDocumentRef, OutcomeAckRequest, PostingWorkItem
from .idempotency import IdempotencyConflict, IdempotencyStore, key_for
from .reasons import FailureKind, scrub_message, to_rejection_reason
from .transport import PostingFeedClient
from .uom import MoneyConformanceError, PreResolvedWarehouse, UnresolvedWarehouse, UomMap


def _ack_key(work_item: PostingWorkItem, outcome: str) -> str:
    """The connectorAckOutcome Idempotency-Key — required on EVERY ack (012, F-004).

    Codex-P1: the key must be **per-outcome**, not per-sale. One sale legitimately yields
    `failed_transient` then `posted` on a re-offer; reusing one key across DIFFERENT outcomes
    returns `409 idempotency_key_conflict` (resolution-concepts.md §4), which would make the
    recovery `posted` ack unreachable after any transient. Keying on `(workItemRef, outcome)`
    keeps each logical outcome's key stable (so a dropped-response resend of the SAME ack still
    dedupes) while letting a later different outcome use its own key. NOT per-attempt — a
    per-attempt nonce would break resend dedup.
    """
    return f"{work_item.work_item_ref}:{outcome}"


def _transient_exceptions() -> tuple[type[BaseException], ...]:
    """The ERPNext/Frappe exceptions that are genuinely retryable (F-005).

    Everything else (ValidationError, PermissionError, KeyError, …) is non-retryable and
    maps to ``permanently_rejected`` — never silently re-offered forever. Resolved lazily so
    the set tracks the installed frappe; unknown names degrade to the base where absent.
    """
    names = ("TimedOutError", "RetryBackoffError", "QueryTimeoutError")
    found = tuple(getattr(frappe, n) for n in names if hasattr(frappe, n))
    # TimeoutError is always a sane transient signal even if frappe names none of the above.
    return (*found, TimeoutError)


def post_work_item(
    work_item: PostingWorkItem,
    *,
    client: PostingFeedClient,
    store: IdempotencyStore,
    uom_map: UomMap,
    warehouses: PreResolvedWarehouse,
    correlation_id: str,
) -> str:
    """Post one work-item to ERPNext and ack the outcome. Returns the resulting outcome string.

    ⏳ BENCH-VALIDATION — exercises live ``frappe`` APIs; validated on staging, not locally.
    """
    key = key_for(work_item)

    # T041 — idempotent replay: an already-posted key echoes the existing documentRef.
    existing = store.get_document_ref(key)
    if existing is not None:
        client.ack_outcome(
            work_item.work_item_ref,
            OutcomeAckRequest.posted(existing),
            idempotency_key=_ack_key(work_item, "posted"),
        )
        _log_signal("posting.replay", work_item, correlation_id)
        return "posted"

    # F-001 — a `reversal` work-item must post a REVERSING document, not a fresh Sales Invoice
    # (012: kind=reversal). The reversal path is not in the interim R1 slice — fail closed
    # rather than mis-post a positive invoice. (Implementing it is a later slice.)
    if work_item.kind != "sale_post":
        return _reject(
            client,
            work_item,
            correlation_id,
            FailureKind.OTHER,
            f"work-item kind {work_item.kind!r} not supported in interim slice (R1)",
        )

    # Build the Sales-Invoice payload from the pure-Python core (no frappe in the build).
    # build_sales_invoice self-validates money (FR-009), raises on an unmapped unit (FR-008) or a
    # non-conformant amount, and warehouse_for raises UnresolvedWarehouse on a store with no
    # pre-resolved warehouse (rider R5 — should have DLQ'd in DP2). All are non-retryable; a final
    # `except Exception` guarantees no build error escapes the terminal-outcome invariant
    # (Codex-P2 / SC-001 / Principle VI).
    try:
        doc_payload = build_sales_invoice(
            work_item, uom_for=uom_map.resolve, warehouse_for=warehouses.for_store
        )
    except UnmappedUnit as exc:
        return _reject(client, work_item, correlation_id, FailureKind.UNMAPPED_UNIT, str(exc))
    except (MoneyConformanceError, UnresolvedWarehouse) as exc:
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:  # any other build error is non-retryable — never let it escape.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    # T031 — submit on ERPNext (interim SI-only; rider R1 — no Payment Entry here).
    try:
        sinv = frappe.get_doc(doc_payload)
        sinv.insert()
        sinv.submit()
        document_ref = ErpnextDocumentRef(doctype="Sales Invoice", name=sinv.name)
    except _transient_exceptions() as exc:
        # T051 — transient (timeout/lock) → failed_transient; DP2 re-offers (no self-retry).
        client.ack_outcome(
            work_item.work_item_ref,
            OutcomeAckRequest.failed_transient(),
            idempotency_key=_ack_key(work_item, "failed_transient"),
        )
        _log_signal("posting.transient", work_item, correlation_id, detail=scrub_message(str(exc)))
        return "failed_transient"
    except frappe.ValidationError as exc:  # type: ignore[attr-defined]
        # T051 — validation failure → permanently_rejected / validation.
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:  # any OTHER error is non-retryable (F-005), not transient.
        # Decision table row 9: an unclassified non-retryable error → permanently_rejected / other.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    # Record the posting, then ack. A concurrent double-record (another worker recorded a
    # different ref for this key first) is resolved by echoing the recorded ref.
    #
    # ⚠️ KNOWN OPEN WINDOW (F-002, NOT closed here): a crash BETWEEN submit and record_posted
    # leaves no record, so a DP2 re-offer would submit a SECOND invoice (the replay_guard finds
    # nothing). IdempotencyConflict only catches concurrent double-record, NOT this crash window.
    # The real fix is ERPNext-side dedup — a unique key on (rt_source_system, rt_external_id),
    # which requires those provenance custom fields to be DECLARED (the deferred custom-field
    # gate, see wave-status) — or a pre-submit pending-record. Deferred to T020 + that gate;
    # the interim slice does NOT yet guarantee exactly-once against a crash (Gate G5 open).
    try:
        store.record_posted(key, document_ref)
    except IdempotencyConflict as conflict:
        document_ref = conflict.existing  # echo the already-recorded document (no duplicate)

    # T032 — ack posted + documentRef; the DP2 sale fact is never mutated.
    client.ack_outcome(
        work_item.work_item_ref,
        OutcomeAckRequest.posted(document_ref),
        idempotency_key=_ack_key(work_item, "posted"),
    )
    _log_signal("posting.posted", work_item, correlation_id, document_ref=document_ref.name)
    return "posted"


def _reject(
    client: PostingFeedClient,
    work_item: PostingWorkItem,
    correlation_id: str,
    kind: FailureKind,
    message: str,
) -> str:
    """Ack a non-retryable failure with a closed-set reason (scrubbed). F-003/F-004.

    Uses the per-outcome ack key for ``permanently_rejected`` (Codex-P1).
    """
    reason = to_rejection_reason(kind, message=message)  # scrubs the message (Gate G4)
    client.ack_outcome(
        work_item.work_item_ref,
        OutcomeAckRequest.permanently_rejected(reason),
        idempotency_key=_ack_key(work_item, "permanently_rejected"),
    )
    _log_signal("posting.rejected", work_item, correlation_id, category=reason.category)
    return "permanently_rejected"


def _log_signal(event: str, work_item: PostingWorkItem, correlation_id: str, **fields) -> None:
    """T090 — structured log carrying the DP2 request_id correlation; never logs secrets/payload."""
    frappe.logger("retail_tower_posting").info(
        {
            "event": event,
            "work_item_ref": work_item.work_item_ref,
            "source_system": work_item.source_system,
            "external_id": work_item.external_id,
            "request_id": correlation_id,
            **fields,
        }
    )
