# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Reversal work-item → reversing-document (return Sales Invoice) builder (Arc A S1).

A 012 ``kind=reversal`` work-item posts a **negative-qty return Sales Invoice** — in ERPNext a
credit note IS a Sales Invoice with ``is_return=1`` (CHECKPOINT-1 decision, chosen for symmetric
DP-017 reconciliation against the 1:1 forward SI). This is a pure dict-transform: no frappe, no
ERPNext call — the bench glue submits the dict.

It COMPOSES on :func:`builder.build_sales_invoice`: that builder validates money on the positive
magnitudes once (FR-009; ``uom.assert_money_conformance`` runs there), so there is a single money
path and no duplicated line loop. This builder then:

  - sets ``is_return = 1`` (credit-note discriminator);
  - **negates** each line's ``qty`` and ``amount`` (return semantics); leaves ``rate`` positive
    (ERPNext convention — the sign lives on qty);
  - overwrites the two provenance fields with the reversal work-item's OWN top-level identity
    (THE F-002 RULE — see below);
  - overwrites ``posting_date`` with the reversal work-item's OWN ``business_date`` (the credit
    note posts in ITS fiscal period, not the original sale snapshot's).

THE CRITICAL CORRECTNESS CONSTRAINT (F-002 forward constraint, wave-status.md): the
``unique_rt_si_provenance`` index spans ALL Sales Invoices via ``rt_external_id``. The reversing
doc MUST carry the reversal work-item's OWN ``work_item.external_id`` in ``rt_external_id`` — NOT
``work_item.reversal_of.external_id`` (nor ``sale.external_id``, the original-sale snapshot). Writing
the original's id would collide with the original SI's unique key and be FALSELY treated as a
dup-recovery. Reading from the top-level ``work_item.*`` also matches what
``frappe_glue._find_posted_invoice`` queries by, keeping a future reversal dup-recovery consistent.

Cardinality: forward sale→SI is 1:1; reversal→original is **N:1** (successive partial returns).
Each reversal work-item has its OWN ``external_id`` / reversal key, so each yields a distinct
``rt_external_id`` even when several share one ``reversal_of``. Idempotency is per reversal-request
key, reusing the same ``store`` replay primitive the sale_post path uses (in the glue leg).

``return_against`` is NOT resolved here: mapping ``reversal_of`` → the original SI's ERPNext docname
needs a DB hit, and this builder's injected signature carries no SI-resolver. The pure builder emits
a standalone ``is_return=1`` credit note (ERPNext accepts that without ``return_against``); the
bench-pending ``frappe_glue`` reversal leg resolves the original SI by
``(reversal_of.source_system, reversal_of.external_id)`` and sets ``return_against`` before insert.
"""

from __future__ import annotations

from collections.abc import Callable

from .builder import build_sales_invoice
from .contracts import PostingWorkItem


def _negate(amount: str) -> str:
	"""Flip the sign of an exact-decimal string WITHOUT going through float (FR-009).

	``"2" -> "-2"``, ``"200.00" -> "-200.00"``. Zero (any fractional width) passes through
	unchanged. An ALREADY-NEGATIVE magnitude is a contract violation (reversal lines must carry
	positive magnitudes — the forward builder validated them as such); per the fail-closed
	principle this RAISES rather than silently double-negating into a spurious positive.
	"""
	if amount.startswith("-"):
		raise ValueError(f"cannot negate already-negative magnitude {amount!r}")
	if amount in ("0", "0.0", "0.00", "0.000", "0.0000"):
		return amount
	return f"-{amount}"


def build_reversing_invoice(
	work_item: PostingWorkItem,
	*,
	uom_for: Callable[[str], str],
	warehouse_for: Callable[[str], dict],
	customer_for: Callable[[str], str],
) -> dict:
	"""Build the ERPNext return Sales-Invoice (credit note) payload for one ``reversal`` work-item.

	Resolvers mirror :func:`builder.build_sales_invoice` exactly (UOM / warehouse / customer). The
	money path is the forward builder's (validated once on positive magnitudes); qty/amount are then
	negated. Raises :class:`ValueError` if handed a non-reversal work-item (it would mis-post).
	"""
	if work_item.kind != "reversal":
		raise ValueError(f"build_reversing_invoice expects a reversal work-item, got kind {work_item.kind!r}")

	# Compose on the forward builder: this validates money (FR-009) on the POSITIVE magnitudes and
	# resolves customer/currency/warehouse/UOM identically — one money path, no duplicated loop.
	doc = build_sales_invoice(
		work_item,
		uom_for=uom_for,
		warehouse_for=warehouse_for,
		customer_for=customer_for,
	)

	# A credit note IS a Sales Invoice with is_return=1.
	doc["is_return"] = 1

	# Return semantics: negate qty + amount (the credit note totals are negative); rate stays
	# positive (ERPNext convention — the sign lives on qty). Negation is string-only (no float).
	for item in doc["items"]:
		item["qty"] = _negate(item["qty"])
		item["amount"] = _negate(item["amount"])

	# THE F-002 RULE: the reversing doc's provenance is the reversal work-item's OWN top-level
	# identity — NOT the original sale's (reversal_of.* / sale.*). The forward builder wrote
	# sale.external_id / sale.source_system; overwrite both with work_item.* so the unique
	# provenance index does not collide with the original SI's slot.
	doc["rt_source_system"] = work_item.source_system
	doc["rt_external_id"] = work_item.external_id

	# The credit note posts in the REVERSAL's fiscal period (its own businessDate), not the
	# original sale snapshot's. The forward builder set sale.business_date — overwrite it.
	doc["posting_date"] = work_item.business_date

	return doc
