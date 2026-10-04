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

from datetime import datetime, timezone

import frappe

from .builder import UnmappedUnit, build_sales_invoice
from .contracts import ErpnextDocumentRef, OutcomeAckRequest, PostingWorkItem
from .idempotency import IdempotencyConflict, IdempotencyStore, key_for, provenance_id
from .posting_time import PostingClock, PostingStamp, apply_stamp, raise_to_original, stamp_for
from .reasons import FailureKind, scrub_message, to_rejection_reason
from .return_builder import (
    MissingRefundTenders,
    ReturnPricingMismatch,
    ReturnResolvers,
    ReturnTaxNotPosted,
    build_return_invoice,
)
from .reversal_builder import build_reversing_invoice, reversal_stamp_source
from .reversal_policy import UnsupportedReversal, assert_reversal_supported
from .stock_policy import (
    ReturnLineMismatch,
    UnsupportedTrackedItem,
    assert_no_tracked_items,
    link_return_to_original,
    link_void_to_original,
    tracking_item_codes,
)
from .tender import (
    SETTLED_FIELDS,
    SettlementDrift,
    TenderMismatch,
    TenderModeMap,
    UnmappedTender,
    assert_settled,
    payments_total,
)
from .transport import PostingFeedClient
from .uom import (
    MoneyConformanceError,
    PreResolvedWarehouse,
    StoreCustomerMap,
    UnmappedStore,
    UnresolvedWarehouse,
    UomMap,
)


def _ack_key(work_item: PostingWorkItem, outcome: str) -> str:
    """The connectorAckOutcome Idempotency-Key — required on EVERY ack (012, F-004).

    Codex-P1: the key must be **per-outcome**, not per-sale. One sale legitimately yields
    `failed_transient` then `posted` on a re-offer; reusing one key across DIFFERENT outcomes
    returns `409 idempotency_key_conflict` (resolution-concepts.md §4), which would make the
    recovery `posted` ack unreachable after any transient. Keying on `(workItemRef, outcome)`
    keeps each logical outcome's key stable (so a dropped-response resend of the SAME ack still
    dedupes) while letting a later different outcome use its own key. NOT per-attempt — a
    per-attempt nonce would break resend dedup.

    RT-171: ``failed_transient`` is the one outcome that legitimately repeats for one work-item —
    DP2 re-offers it after each transient, and each re-offer is a NEW logical ack that must reach
    the handler (it re-heads the row and spends one unit of DP2's retry budget). Backend-Core's
    ack route is ``@Idempotent``: a second ``{workItemRef}:failed_transient`` would be REPLAYED
    from the stored response without running the handler, leaving the row pending forever. So the
    transient key also carries the offer's ``itemCursor``: stable across resends of ONE offer (resend
    dedup still holds) and different across re-offers (DP2 issues a new cursor per offer). The
    terminal ``posted`` / ``permanently_rejected`` keys are unchanged — they happen at most once.
    """
    if outcome == "failed_transient":
        return f"{work_item.work_item_ref}:failed_transient:{work_item.item_cursor}"
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


def _dup_provenance_exceptions() -> tuple[type[BaseException], ...]:
    """Exceptions a duplicate Sales Invoice `(rt_source_system, rt_external_id)` insert raises (G5/F-002).

    The `unique_rt_si_provenance` index on Sales Invoice (patch sales_invoice_unique_provenance)
    makes a SECOND submit of an already-posted sale fail at the DB. On bench frappe v15 this surfaces
    as **UniqueValidationError** (a ValidationError subclass — verified on the bench, NOT guessed);
    DuplicateEntryError is included defensively (the Posting Log path raises that one). getattr-guarded
    so a frappe missing a name degrades rather than errors. This MUST be caught BEFORE the generic
    `frappe.ValidationError` handler, or a legitimate crash-recovery would be FALSELY rejected.
    """
    names = ("UniqueValidationError", "DuplicateEntryError")
    return tuple(
        exc for exc in (getattr(frappe.exceptions, n, None) for n in names) if exc is not None
    ) or (Exception,)


def _find_posted_invoice(work_item: PostingWorkItem) -> ErpnextDocumentRef | None:
    """Resolve the already-submitted Sales Invoice for this work-item's provenance (G5/F-002 recovery).

    Looks up by the `(rt_source_system, rt_external_id)` idempotency anchor — a hit IS the same
    logical posting. The `rt_external_id` value is the #28 discriminator `provenance_id(work_item)`:
    `external_id` for a `sale_post` (UNCHANGED forward recovery), `work_item_ref` for a `reversal`.
    This MUST mirror what the builder wrote (`reversal_builder` writes the same `provenance_id`),
    else a reversal crash-recovery would match the ORIGINAL forward SI by `external_id` and echo it
    (re-introducing the #28 silent mis-success on the dup path). Returns the document_ref to echo,
    or None if no submitted SI exists.
    """
    name = frappe.db.get_value(
        "Sales Invoice",
        {
            "rt_source_system": work_item.source_system,
            "rt_external_id": provenance_id(work_item),
            "docstatus": 1,
        },
        "name",
    )
    if not name:
        return None
    return ErpnextDocumentRef(doctype="Sales Invoice", name=name)


def post_work_item(
    work_item: PostingWorkItem,
    *,
    client: PostingFeedClient,
    store: IdempotencyStore,
    uom_map: UomMap,
    warehouses: PreResolvedWarehouse,
    customers: StoreCustomerMap,
    tenders: TenderModeMap,
    correlation_id: str,
) -> str:
    """Post one work-item to ERPNext and ack the outcome. Returns the resulting outcome string.

    ⏳ BENCH-VALIDATION — exercises live ``frappe`` APIs; validated on staging, not locally.
    ``tenders`` is the RT-10 D5 tender → Mode of Payment map (RT-78): a sale carrying tenders is
    settled on the invoice and an unmapped method fails closed. A void does not use it — it pays
    back the original invoice's own payment rows.
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

    # F-001 — a `reversal` work-item posts a REVERSING document (a return Sales Invoice,
    # `is_return=1`), NOT a fresh positive Sales Invoice (012: kind=reversal). Arc A S1 routes it
    # to the dedicated reversal leg below. Any unknown kind still fails closed.
    if work_item.kind == "reversal":
        return _post_reversal(
            work_item,
            client=client,
            store=store,
            uom_map=uom_map,
            warehouses=warehouses,
            customers=customers,
            tenders=tenders,
            correlation_id=correlation_id,
        )
    if work_item.kind != "sale_post":
        return _reject(
            client,
            work_item,
            correlation_id,
            FailureKind.OTHER,
            f"work-item kind {work_item.kind!r} not supported (012 kinds: sale_post, reversal)",
        )

    # Build the Sales-Invoice payload from the pure-Python core (no frappe in the build).
    # build_sales_invoice self-validates money (FR-009), raises on an unmapped unit (FR-008) or a
    # non-conformant amount, and warehouse_for raises UnresolvedWarehouse on a store with no
    # pre-resolved warehouse (rider R5 — should have DLQ'd in DP2). All are non-retryable; a final
    # `except Exception` guarantees no build error escapes the terminal-outcome invariant
    # (Codex-P2 / SC-001 / Principle VI).
    try:
        stamp = _posting_stamp(work_item, work_item.sale.business_date)
        doc_payload = build_sales_invoice(
            work_item,
            uom_for=uom_map.resolve,
            warehouse_for=warehouses.for_store,
            customer_for=customers.for_store,
            posting_stamp=stamp,
            mode_of_payment_for=tenders.resolve,
        )
    except UnmappedUnit as exc:
        return _reject(client, work_item, correlation_id, FailureKind.UNMAPPED_UNIT, str(exc))
    except (MoneyConformanceError, UnresolvedWarehouse, UnmappedStore, UnmappedTender, TenderMismatch) as exc:
        # UnmappedStore (F-009): a store with no configured Customer fails closed → validation,
        # exactly like an unresolved warehouse — never fabricate a customer (Principle VI).
        # RT-78: an unmapped tender method (D5) or a tender total that differs from the lines
        # (amendment 4a) is the same — the connector never guesses a mode or forces a match.
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:  # any other build error is non-retryable — never let it escape.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    _log_stamp_adjustments(stamp, work_item, correlation_id)

    # RT-48 / RT-47 D4 — the sale moves stock, so a batch/serial Item fails closed (ERPNext would
    # otherwise auto-pick a batch, i.e. guess one). After the replay guard, before insert.
    rejected = _guard_tracked_items(doc_payload, work_item, client, correlation_id)
    if rejected is not None:
        return rejected

    # T031 — submit on ERPNext (interim SI-only; rider R1 — no Payment Entry here).
    try:
        sinv = _submit_atomically(doc_payload)
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
    except SettlementDrift as exc:
        # RT-78 — ERPNext's computed totals left change/outstanding/write-off on a settled invoice.
        # _submit_atomically already rolled the insert back; nothing was submitted. Caught BEFORE the
        # dup-provenance clause, whose fallback catches Exception on a frappe missing those names.
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except _dup_provenance_exceptions() as exc:
        # GATE G5 / F-002 — the crash-window recovery. The `unique_rt_si_provenance` index rejected
        # a SECOND submit of an already-posted sale (a crash between the FIRST submit and
        # record_posted left no Posting Log row, so the replay guard above found nothing). This is
        # NOT a rejection: a matching SI already exists. Resolve to it (echo its documentRef), back-
        # fill the Posting Log so future re-offers fast-path through the replay guard, and fall
        # through to the normal `posted` ack. Catching this BEFORE frappe.ValidationError is load-
        # bearing — UniqueValidationError ⊂ ValidationError, so the generic handler would otherwise
        # FALSELY reject a legitimately-posted sale (Principle VI inversion).
        existing = _find_posted_invoice(work_item)
        if existing is None:
            # Dup index fired but no SI found under our provenance — genuinely unexpected; do not
            # fabricate success. Treat as a non-retryable error (never a silent partial).
            return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))
        document_ref = existing
        try:
            store.record_posted(key, document_ref)  # back-fill the missing Posting Log row
        except IdempotencyConflict as conflict:
            document_ref = conflict.existing
        client.ack_outcome(
            work_item.work_item_ref,
            OutcomeAckRequest.posted(document_ref),
            idempotency_key=_ack_key(work_item, "posted"),
        )
        _log_signal("posting.recovered", work_item, correlation_id, document_ref=document_ref.name)
        return "posted"
    except frappe.ValidationError as exc:  # type: ignore[attr-defined]
        # T051 — validation failure → permanently_rejected / validation.
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:  # any OTHER error is non-retryable (F-005), not transient.
        # Decision table row 9: an unclassified non-retryable error → permanently_rejected / other.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    # Record the posting, then ack. A concurrent double-record (another worker recorded a
    # different ref for this key first) is resolved by echoing the recorded ref.
    #
    # F-002 (the crash-BETWEEN-submit-and-record window) is now CLOSED by the
    # `unique_rt_si_provenance` index on Sales Invoice + the `_dup_provenance_exceptions` recovery
    # above: if a crash here leaves no Posting Log row, a DP2 re-offer's second submit fails on the
    # unique index, is caught, and resolves to the existing SI (no duplicate). Gate G5 holds against
    # both concurrent double-record (this IdempotencyConflict echo) and the crash window.
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


def _resolve_original_invoice(work_item: PostingWorkItem) -> str | None:
    """Resolve the ORIGINAL submitted Sales Invoice this reversal targets (Arc A S1).

    ⏳ BENCH-VALIDATION. Looks up the forward SI by the reversed sale's provenance
    ``(reversal_of.source_system, reversal_of.external_id)`` — the 012 ``reversalOf`` anchor, which
    is the original sale's ``(sourceSystem, externalId)``, NOT this reversal work-item's own id.
    Returns the original SI's ERPNext docname for ``return_against``, or None if none is found
    (the caller fails closed — never post a reversal against a sale that was never posted).
    """
    if work_item.reversal_of is None:  # an upstream contract violation for kind=reversal.
        return None
    return frappe.db.get_value(
        "Sales Invoice",
        {
            "rt_source_system": work_item.reversal_of.source_system,
            "rt_external_id": work_item.reversal_of.external_id,
            "docstatus": 1,
        },
        "name",
    )


def _post_reversal(
    work_item: PostingWorkItem,
    *,
    client: PostingFeedClient,
    store: IdempotencyStore,
    uom_map: UomMap,
    warehouses: PreResolvedWarehouse,
    customers: StoreCustomerMap,
    tenders: TenderModeMap,
    correlation_id: str,
) -> str:
    """Post one ``reversal`` work-item as a return Sales Invoice (credit note). Returns the outcome.

    ⏳ BENCH-VALIDATION — this leg exercises live ``frappe`` APIs and CANNOT run in this
    environment (no Frappe bench; standing-rules §6). It mirrors the sale_post path exactly:
    replay-guard → build (pure ``build_reversing_invoice``) → resolve original for return_against →
    ``insert().submit()`` → record_posted → ack ``posted``; transient/validation/dup/other handling
    mirrors the forward path; an unresolvable original sale fails CLOSED (Principle VI — never post a
    reversal against a sale that was never posted). Idempotency reuses the SAME ``store`` replay
    primitive but keyed on the reversal work-item's ``(source_system, work_item_ref)`` (Connector
    #28 re-key via :func:`key_for` — the top-level ``external_id`` on a reversal is the ORIGINAL
    sale's id and would collide with its replay slot). No new primitive (Arc A §4); a
    reversal→original is N:1 but each reversal request is 1:1 with its key.
    """
    key = key_for(work_item)

    # Replay guard: an already-posted reversal key echoes the existing reversing-doc ref (T041).
    existing = store.get_document_ref(key)
    if existing is not None:
        client.ack_outcome(
            work_item.work_item_ref,
            OutcomeAckRequest.posted(existing),
            idempotency_key=_ack_key(work_item, "posted"),
        )
        _log_signal("posting.replay", work_item, correlation_id)
        return "posted"

    # RT-71 (RT-14 F1 / D8) — an amount-only refund would credit the WHOLE sale (the feed carries
    # every sale line and no refund amount). Reject it before building anything. AFTER the replay
    # guard, so an already-posted legacy refund still echoes its document.
    try:
        assert_reversal_supported(work_item)
    except UnsupportedReversal as exc:
        return _recover_or_reject_unsupported(
            work_item, key, exc, client=client, store=store, correlation_id=correlation_id
        )

    # Build the reversing payload from the pure core (no frappe in the build). Same fail-closed
    # mapping as the forward path: unmapped unit → unmapped_unit; money/warehouse/store → validation;
    # anything else → other. A final `except Exception` guarantees the terminal-outcome invariant.
    try:
        # RT-16 / RT-63: the reversal's own recordedAt + businessDate (RT-49 fallback when absent).
        stamp = stamp_for(*reversal_stamp_source(work_item), _posting_clock())
        doc_payload = _build_reversal(
            work_item, stamp, uom_map=uom_map, warehouses=warehouses, customers=customers, tenders=tenders
        )
    except UnmappedUnit as exc:
        return _reject(client, work_item, correlation_id, FailureKind.UNMAPPED_UNIT, str(exc))
    except (
        MoneyConformanceError,
        UnresolvedWarehouse,
        UnmappedStore,
        UnmappedTender,
        TenderMismatch,
        MissingRefundTenders,
        ReturnPricingMismatch,
        ReturnTaxNotPosted,
    ) as exc:
        # RT-16: a return without refundTenders, or priced other than unitPrice x qty, is rejected
        # like an unmapped store — never posted as an outstanding credit note or at a guessed amount.
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:  # any other build error is non-retryable — never let it escape.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    # Resolve the original SI for `return_against`. Fail CLOSED if the reversed sale was never
    # posted (no submitted forward SI) — posting a reversal against a non-existent sale would be a
    # silent inconsistency (Principle VI). The pure builder cannot do this lookup (no DB hit there),
    # so it is applied here, on the bench leg, before insert.
    original_name = _resolve_original_invoice(work_item)
    if original_name is None:
        return _reject(
            client,
            work_item,
            correlation_id,
            FailureKind.VALIDATION,
            "reversal targets a sale with no submitted Sales Invoice (return_against unresolved)",
        )
    doc_payload["return_against"] = original_name

    # RT-49 (decision 10312) — ERPNext rejects a return timestamped EARLIER than its original. An
    # original posted before RT-49 carries ERPNext's post-day, which can be after the businessDate
    # stamp; raise to it (equal is allowed). Applies to every reversal kind.
    try:
        original_date, original_time = _read_original_posting(original_name)
        stamp = raise_to_original(stamp, original_date, original_time)
        doc_payload = apply_stamp(doc_payload, stamp)
    except Exception as exc:  # a read failure must not escape the terminal-outcome invariant.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))
    _log_stamp_adjustments(stamp, work_item, correlation_id)

    # RT-48 / RT-47 D5 — a full void mirrors the original's update_stock (a legacy update_stock=0
    # sale never fabricates a stock restoration) and, RT-80, its disable_rounded_total (a pre-RT-80
    # rounded sale is reversed with its own Round Off), and links each line to its original row so
    # ERPNext's per-line over-return cap applies. A refund stays update_stock=0 and unlinked (its
    # line semantics belong to RT-14/RT-16). Any line mismatch fails closed.
    # RT-16 / RT-14 D6 — a partial return links each row to the original row with the same
    # rt_line_ref (identity), restores to that row's warehouse and mirrors update_stock.
    kind = work_item.reversal_of.reversal_kind if work_item.reversal_of is not None else None
    if kind in ("void", "return"):
        try:
            doc_payload = _link_to_original(kind, doc_payload, _read_original_invoice(original_name))
        except ReturnLineMismatch as exc:
            return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
        except Exception as exc:  # a read failure must not escape the terminal-outcome invariant.
            return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    rejected = _guard_tracked_items(doc_payload, work_item, client, correlation_id)
    if rejected is not None:
        return rejected

    # Submit on ERPNext. The `unique_rt_si_provenance` index spans ALL Sales Invoices (incl.
    # is_return=1), so a second submit of the SAME reversal key (its work_item_ref) collides and is
    # recovered exactly like the forward path — and because the builder wrote the reversal's
    # work_item_ref into rt_external_id (#28 re-key), it does NOT collide with the original SI's slot.
    try:
        sinv = _submit_atomically(doc_payload)
        document_ref = ErpnextDocumentRef(doctype="Sales Invoice", name=sinv.name)
    except _transient_exceptions() as exc:
        client.ack_outcome(
            work_item.work_item_ref,
            OutcomeAckRequest.failed_transient(),
            idempotency_key=_ack_key(work_item, "failed_transient"),
        )
        _log_signal("posting.transient", work_item, correlation_id, detail=scrub_message(str(exc)))
        return "failed_transient"
    except SettlementDrift as exc:
        # RT-78 — ERPNext's computed totals left change/outstanding/write-off on a settled invoice.
        # _submit_atomically already rolled the insert back; nothing was submitted. Caught BEFORE the
        # dup-provenance clause, whose fallback catches Exception on a frappe missing those names.
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except _dup_provenance_exceptions() as exc:
        # Crash-window recovery, keyed on the reversal's work_item_ref provenance (#28 re-key): a
        # re-offer whose second submit hits the unique index resolves to the already-posted
        # reversing doc (via _find_posted_invoice, which reads the same provenance_id discriminator).
        recovered = _find_posted_invoice(work_item)
        if recovered is None:
            return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))
        document_ref = recovered
        try:
            store.record_posted(key, document_ref)
        except IdempotencyConflict as conflict:
            document_ref = conflict.existing
        client.ack_outcome(
            work_item.work_item_ref,
            OutcomeAckRequest.posted(document_ref),
            idempotency_key=_ack_key(work_item, "posted"),
        )
        _log_signal("posting.recovered", work_item, correlation_id, document_ref=document_ref.name)
        return "posted"
    except frappe.ValidationError as exc:  # type: ignore[attr-defined]
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:  # any OTHER error is non-retryable (F-005), not transient.
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))

    try:
        store.record_posted(key, document_ref)
    except IdempotencyConflict as conflict:
        document_ref = conflict.existing

    client.ack_outcome(
        work_item.work_item_ref,
        OutcomeAckRequest.posted(document_ref),
        idempotency_key=_ack_key(work_item, "posted"),
    )
    _log_signal("posting.posted", work_item, correlation_id, document_ref=document_ref.name)
    return "posted"


def _recover_or_reject_unsupported(
    work_item: PostingWorkItem,
    key,
    exc: UnsupportedReversal,
    *,
    client: PostingFeedClient,
    store: IdempotencyStore,
    correlation_id: str,
) -> str:
    """Reject an unsupported reversal, unless its invoice already exists (RT-71; Codex P1, PR #46).

    A legacy refund may have been submitted before RT-71 and then crashed before ``record_posted``:
    the Posting Log has no row, so the replay guard missed it, but the Sales Invoice exists under
    this work-item's provenance. Rejecting it would make DP2 disagree with ERPNext, and a later
    ``re_post`` could credit the sale twice. So resolve that invoice first and ack it ``posted``
    (back-filling the Posting Log), exactly like the duplicate-provenance recovery. Otherwise nothing
    was posted, and the reversal is rejected as ``validation``.
    """
    existing = _find_posted_invoice(work_item)
    if existing is None:
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    document_ref = existing
    try:
        store.record_posted(key, document_ref)
    except IdempotencyConflict as conflict:
        document_ref = conflict.existing
    client.ack_outcome(
        work_item.work_item_ref,
        OutcomeAckRequest.posted(document_ref),
        idempotency_key=_ack_key(work_item, "posted"),
    )
    _log_signal("posting.recovered", work_item, correlation_id, document_ref=document_ref.name)
    return "posted"


_SUBMIT_SAVEPOINT = "rt_posting_submit"


def _submit_atomically(doc_payload: dict):
    """Insert + submit one Sales Invoice as a unit: on ANY failure, undo it before re-raising (RT-48).

    ⏳ BENCH-VALIDATION. A submit can fail PART-WAY. The RT-48 bench run proved it: a missing
    valuation rate raised after the invoice row and its Stock Ledger Entry were written, and the
    scheduler job then committed that half-posted invoice while the connector acked
    ``permanently_rejected``. Stock and ERP truth would diverge from the DP2 outcome (Principle VI).
    Rolling back to a savepoint keeps "rejected" meaning "nothing posted", so the later ``re_post``
    repair starts clean. The caller's exception mapping is unchanged.
    """
    frappe.db.savepoint(_SUBMIT_SAVEPOINT)
    try:
        sinv = frappe.get_doc(doc_payload)
        sinv.insert()
        if doc_payload.get("payments"):
            # RT-78: verify ERPNext's computed totals settle the invoice exactly before submitting.
            assert_settled(
                {field: sinv.get(field) for field in SETTLED_FIELDS},
                expected_total=payments_total(doc_payload["payments"]),
            )
        sinv.submit()
    except BaseException:
        frappe.db.rollback(save_point=_SUBMIT_SAVEPOINT)
        raise
    return sinv


def _read_item_tracking(doc_payload: dict) -> dict[str, dict]:
    """Read ``{item_code: {has_batch_no, has_serial_no}}`` for a stock-moving doc's Items (RT-48).

    ⏳ BENCH-VALIDATION. Returns ``{}`` for a doc that does not move stock (nothing to check).
    """
    codes = tracking_item_codes(doc_payload)
    if not codes or not doc_payload.get("update_stock"):
        return {}
    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", codes]},
        fields=["name", "has_batch_no", "has_serial_no"],
    )
    return {row["name"]: row for row in rows}


def _guard_tracked_items(
    doc_payload: dict,
    work_item: PostingWorkItem,
    client: PostingFeedClient,
    correlation_id: str,
) -> str | None:
    """Reject a stock-moving doc carrying a batch/serial Item (RT-47 D4). Returns the outcome if rejected.

    ⏳ BENCH-VALIDATION. The decision is the pure ``stock_policy.assert_no_tracked_items``; this
    only reads the Item flags. A read failure is non-retryable ``other`` (never escapes the page).
    """
    try:
        assert_no_tracked_items(doc_payload, _read_item_tracking(doc_payload))
    except UnsupportedTrackedItem as exc:
        return _reject(client, work_item, correlation_id, FailureKind.VALIDATION, str(exc))
    except Exception as exc:
        return _reject(client, work_item, correlation_id, FailureKind.OTHER, str(exc))
    return None


def _posting_clock() -> PostingClock:
    """The ERPNext site timezone (ERPNext reads ``posting_time`` as site-local) and now (RT-49).

    ⏳ BENCH-VALIDATION.
    """
    return PostingClock(site_tz=frappe.utils.get_system_timezone(), now=datetime.now(timezone.utc))


def _posting_stamp(work_item: PostingWorkItem, business_date: str) -> PostingStamp:
    """RT-49 rule (``posting_time.stamp_for``) for this work-item on the live site clock."""
    return stamp_for(work_item.sale.occurred_at, business_date, _posting_clock())


def _read_original_posting(name: str) -> tuple[object, object]:
    """Read the original SI's ``(posting_date, posting_time)`` as stored (RT-49).

    ⏳ BENCH-VALIDATION. ``posting_time`` comes back from MariaDB as a ``timedelta``;
    ``posting_time.raise_to_original`` normalises it.
    """
    row = frappe.db.get_value("Sales Invoice", name, ["posting_date", "posting_time"], as_dict=True)
    if not row:
        raise ValueError(f"original Sales Invoice {name!r} not readable for its posting time")
    return row["posting_date"], row["posting_time"]


def _log_stamp_adjustments(stamp: PostingStamp, work_item: PostingWorkItem, correlation_id: str) -> None:
    """Log a clamped/capped/raised posting stamp at ERROR (Frappe drops lower levels; RT-49 10312).

    A clamp means the store and site timezones disagree (a precondition breach) or the POS clock
    ran ahead; a raise means the original invoice was posted before RT-49 on a later day.
    """
    if not stamp.adjustments:
        return
    frappe.logger("retail_tower_posting").error(
        {
            "event": "posting.time_adjusted",
            "work_item_ref": work_item.work_item_ref,
            "source_system": work_item.source_system,
            "external_id": work_item.external_id,
            "request_id": correlation_id,
            "adjustments": list(stamp.adjustments),
            "posting_date": stamp.posting_date,
            "posting_time": stamp.posting_time,
        }
    )


def _build_reversal(
    work_item: PostingWorkItem,
    stamp: PostingStamp,
    *,
    uom_map: UomMap,
    warehouses: PreResolvedWarehouse,
    customers: StoreCustomerMap,
    tenders: TenderModeMap,
) -> dict:
    """The pure reversing payload: a partial return (RT-16) or a void/refund credit note.

    A void takes no tender map (its Modes of Payment come from the original invoice, RT-78); a
    return pays its refund out through the CURRENT map (a new cash payout, RT-10 D6).
    """
    if work_item.reversal_of is not None and work_item.reversal_of.reversal_kind == "return":
        resolvers = ReturnResolvers(
            uom_for=uom_map.resolve,
            warehouse_for=warehouses.for_store,
            customer_for=customers.for_store,
            mode_of_payment_for=tenders.resolve,
        )
        return build_return_invoice(work_item, resolvers, posting_stamp=stamp)
    return build_reversing_invoice(
        work_item,
        uom_for=uom_map.resolve,
        warehouse_for=warehouses.for_store,
        customer_for=customers.for_store,
        posting_stamp=stamp,
    )


def _link_to_original(kind: str, doc_payload: dict, original: dict) -> dict:
    """Mirror/link a void (whole sale) or a partial return (by rt_line_ref) onto its original invoice."""
    if kind == "return":
        return link_return_to_original(
            doc_payload,
            original_update_stock=original["update_stock"],
            original_items=original["items"],
            original_customer=original["customer"],
        )
    return link_void_to_original(
        doc_payload,
        original_update_stock=original["update_stock"],
        original_disable_rounded_total=original["disable_rounded_total"],
        original_items=original["items"],
        original_is_pos=original["is_pos"],
        original_payments=original["payments"],
    )


def _read_original_invoice(name: str) -> dict:
    """Read what a full void mirrors from the original SI (``stock_policy.link_void_to_original``).

    ``update_stock`` (RT-48), ``disable_rounded_total`` (RT-80), ``is_pos`` and its payment rows
    ``(mode_of_payment, amount, idx)`` (RT-78), and its item rows
    ``(name, item_code, qty, idx, warehouse, rt_line_ref, uom)`` (RT-48; ``rt_line_ref``/``uom`` RT-16)
    and the ``customer`` a partial return credits. The
    rows are filtered by ``parent`` — the original only, never an earlier credit note's rows.

    ⏳ BENCH-VALIDATION.
    """
    flags = frappe.db.get_value(
        "Sales Invoice", name, ["update_stock", "disable_rounded_total", "is_pos", "customer"], as_dict=True
    ) or {}
    rows = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": name, "parenttype": "Sales Invoice"},
        fields=["name", "item_code", "qty", "idx", "warehouse", "rt_line_ref", "uom", "conversion_factor"],
        order_by="idx asc",
    )
    payments = frappe.get_all(
        "Sales Invoice Payment",
        filters={"parent": name, "parenttype": "Sales Invoice"},
        fields=["mode_of_payment", "amount", "idx"],
        order_by="idx asc",
    )
    return {
        "update_stock": int(flags.get("update_stock") or 0),
        "disable_rounded_total": int(flags.get("disable_rounded_total") or 0),
        "is_pos": int(flags.get("is_pos") or 0),
        "customer": flags.get("customer"),
        "items": [dict(row) for row in rows],
        "payments": [dict(row) for row in payments],
    }


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
