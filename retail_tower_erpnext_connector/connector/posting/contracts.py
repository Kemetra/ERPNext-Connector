# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Frozen read-models for the fixed 012 posting-feed contract (T010).

These mirror Data-Pulse-2's ``posting-feed.yaml`` (1.1.0-draft) 1:1. The contract is
DP2-owned and read-only (FR-015, Principle I) — these DTOs CITE it, never re-derive it.

Apply-only invariant (rider R2 / Q-CON-004): every offered ``SaleLine`` carries a
DP2-resolved ``erpnextItemRef``. A line missing it is an upstream contract violation —
parsing raises :class:`MissingErpnextItemRef` (the connector never resolves/guesses; FR-001).

This module imports NO frappe — it is the pure-Python core and is unit-tested locally.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# 012 RejectionReason.category — the closed set. No new wire reason is ever invented
# (FR-007). An unmapped unit is a `validation` failure (there is no `unmapped_uom`).
REJECTION_CATEGORIES: frozenset[str] = frozenset(
    {"validation", "closed_period", "unmapped_item", "unmapped_account", "other"}
)

# 012 OutcomeAckRequest.outcome enum.
OUTCOMES: frozenset[str] = frozenset({"posted", "failed_transient", "permanently_rejected"})

# 012 PostingWorkItem.kind enum.
WORK_ITEM_KINDS: frozenset[str] = frozenset({"sale_post", "reversal"})

# 012 ReversalRef.reversalKind enum.
REVERSAL_KINDS: frozenset[str] = frozenset({"void", "refund"})


class MissingErpnextItemRef(Exception):
    """An offered SaleLine lacks ``erpnextItemRef`` — an upstream 012 contract violation.

    Per rider R2 every offered line is DP2-pre-resolved; observing one without the ref is a
    STOP-and-raise (the connector never substitutes a "Misc" item — R3). Mapped to a
    ``permanently_rejected`` / ``validation`` outcome by the caller (FR-006/008).
    """


@dataclass(frozen=True)
class ErpnextItemRef:
    """012 ``ErpnextItemRef`` — generic ``{doctype:"Item", name}`` addressing (O-6)."""

    doctype: str
    name: str

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> ErpnextItemRef:
        doctype = wire.get("doctype")
        if doctype != "Item":
            raise ValueError(f"ErpnextItemRef.doctype must be 'Item', got {doctype!r}")
        return cls(doctype="Item", name=str(wire["name"]))


@dataclass(frozen=True)
class ErpnextDocumentRef:
    """012 ``ErpnextDocumentRef`` — generic addressing for a submitted ERPNext document."""

    doctype: str
    name: str

    def to_wire(self) -> dict[str, str]:
        return {"doctype": self.doctype, "name": self.name}


@dataclass(frozen=True)
class ReversalRef:
    """012 ``ReversalRef`` — provenance of the original sale a reversal targets (O-4)."""

    source_system: str
    external_id: str
    reversal_kind: str

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> ReversalRef:
        kind = str(wire["reversalKind"])
        if kind not in REVERSAL_KINDS:
            raise ValueError(f"reversalKind must be one of {sorted(REVERSAL_KINDS)}, got {kind!r}")
        return cls(
            source_system=str(wire["sourceSystem"]),
            external_id=str(wire["externalId"]),
            reversal_kind=kind,
        )


@dataclass(frozen=True)
class SaleLine:
    """012 ``SaleLine`` — a frozen 008 sale-line snapshot carrying the resolved Item identity.

    Money fields are exact-decimal strings (never float — FR-009 / `DecimalAmount`).
    """

    line_name: str
    unit_price: str
    currency_code: str
    quantity: str
    line_amount: str
    unit: str
    erpnext_item_ref: ErpnextItemRef
    tax_amount: str | None = None
    tenant_product_ref: str | None = None

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> SaleLine:
        if "erpnextItemRef" not in wire or wire.get("erpnextItemRef") is None:
            raise MissingErpnextItemRef(
                f"offered SaleLine {wire.get('lineName')!r} carries no erpnextItemRef "
                "(rider R2 — every offered line is DP2-pre-resolved)"
            )
        return cls(
            line_name=str(wire["lineName"]),
            unit_price=str(wire["unitPrice"]),
            currency_code=str(wire["currencyCode"]),
            quantity=str(wire["quantity"]),
            line_amount=str(wire["lineAmount"]),
            unit=str(wire["unit"]),
            erpnext_item_ref=ErpnextItemRef.from_wire(wire["erpnextItemRef"]),  # type: ignore[arg-type]
            tax_amount=None if wire.get("taxAmount") is None else str(wire["taxAmount"]),
            tenant_product_ref=(
                None if wire.get("tenantProductRef") is None else str(wire["tenantProductRef"])
            ),
        )


@dataclass(frozen=True)
class Sale:
    """012 ``Sale`` — wire projection of a captured 008 sale (header + lines)."""

    sale_ref: str
    store_id: str
    currency_code: str
    pos_total: str
    occurred_at: str
    business_date: str
    source_system: str
    external_id: str
    lines: tuple[SaleLine, ...]

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> Sale:
        # 012 Sale.lines is minItems: 1 — an empty lines array is an upstream contract
        # violation; raise rather than build an invoice with no items (F-012).
        raw_lines = wire["lines"]
        if not raw_lines:
            raise ValueError("Sale.lines must carry at least one line (012 minItems: 1)")
        return cls(
            sale_ref=str(wire["saleRef"]),
            store_id=str(wire["storeId"]),
            currency_code=str(wire["currencyCode"]),
            pos_total=str(wire["posTotal"]),
            occurred_at=str(wire["occurredAt"]),
            business_date=str(wire["businessDate"]),
            source_system=str(wire["sourceSystem"]),
            external_id=str(wire["externalId"]),
            lines=tuple(SaleLine.from_wire(line) for line in raw_lines),  # type: ignore[union-attr]
        )


@dataclass(frozen=True)
class PostingWorkItem:
    """012 ``PostingWorkItem`` — one pending posting the connector must apply (O-1)."""

    work_item_ref: str
    kind: str
    source_system: str
    external_id: str
    payload_hash: str
    business_date: str
    sale: Sale
    item_cursor: str
    reversal_of: ReversalRef | None = None

    @classmethod
    def from_wire(cls, wire: Mapping[str, object]) -> PostingWorkItem:
        kind = str(wire["kind"])
        if kind not in WORK_ITEM_KINDS:
            raise ValueError(f"kind must be one of {sorted(WORK_ITEM_KINDS)}, got {kind!r}")
        reversal_of = wire.get("reversalOf")
        return cls(
            work_item_ref=str(wire["workItemRef"]),
            kind=kind,
            source_system=str(wire["sourceSystem"]),
            external_id=str(wire["externalId"]),
            payload_hash=str(wire["payloadHash"]),
            business_date=str(wire["businessDate"]),
            sale=Sale.from_wire(wire["sale"]),  # type: ignore[arg-type]
            item_cursor=str(wire["itemCursor"]),
            reversal_of=None if reversal_of is None else ReversalRef.from_wire(reversal_of),
        )

    @property
    def idempotency_key(self) -> tuple[str, str]:
        """The 012 O-3 wire idempotency anchor — ``(sourceSystem, externalId)``."""
        return (self.source_system, self.external_id)


@dataclass(frozen=True)
class RejectionReason:
    """012 ``RejectionReason`` — structured permanent-rejection reason (closed category set)."""

    category: str
    message: str

    def __post_init__(self) -> None:
        if self.category not in REJECTION_CATEGORIES:
            raise ValueError(
                f"category must be one of {sorted(REJECTION_CATEGORIES)} "
                f"(no new wire reason — FR-007), got {self.category!r}"
            )

    def to_wire(self) -> dict[str, str]:
        return {"category": self.category, "message": self.message}


@dataclass(frozen=True)
class OutcomeAckRequest:
    """012 ``OutcomeAckRequest`` — the typed terminal outcome over ``connectorAckOutcome``."""

    outcome: str
    document_ref: ErpnextDocumentRef | None = None
    reason: RejectionReason | None = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}, got {self.outcome!r}")
        if self.outcome == "posted" and self.document_ref is None:
            raise ValueError("posted outcome requires a documentRef (012 OutcomeAckRequest)")
        if self.outcome == "permanently_rejected" and self.reason is None:
            raise ValueError("permanently_rejected outcome requires a reason (012)")

    @classmethod
    def posted(cls, document_ref: ErpnextDocumentRef) -> OutcomeAckRequest:
        return cls(outcome="posted", document_ref=document_ref)

    @classmethod
    def failed_transient(cls) -> OutcomeAckRequest:
        return cls(outcome="failed_transient")

    @classmethod
    def permanently_rejected(cls, reason: RejectionReason) -> OutcomeAckRequest:
        return cls(outcome="permanently_rejected", reason=reason)

    def to_wire(self) -> dict[str, object]:
        wire: dict[str, object] = {"outcome": self.outcome}
        if self.document_ref is not None:
            wire["documentRef"] = self.document_ref.to_wire()
        if self.reason is not None:
            wire["reason"] = self.reason.to_wire()
        return wire
