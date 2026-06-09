# Reversal-apply slice — decision & status (Arc A S1)

Branch: `feat/006-reversal-apply`. Scope: route 012 `kind=reversal` work-items to a reversing
ERPNext document. Touches ONLY the Connector repo's posting layer + its tests.

## CHECKPOINT-1 — reversing document type (decided, not re-opened here)

A reversal posts a **negative-qty return Sales Invoice** — in ERPNext a credit note IS a Sales
Invoice with `is_return=1`. Chosen for **symmetric DP-017 reconciliation** against the 1:1 forward
SI: the reversing doc lands in the same doctype / provenance space as the sale it reverses, so
reconciliation compares like with like (forward SI vs return SI) rather than across doctypes.

## F-002 handling — the critical correctness constraint

The `unique_rt_si_provenance` index spans **ALL** Sales Invoices via `rt_external_id` (a credit
note is a Sales Invoice, so it shares the index). The reversing builder therefore writes the
reversal work-item's **OWN top-level** `work_item.external_id` (and `work_item.source_system`) into
`rt_external_id` / `rt_source_system` — **NOT** `reversal_of.external_id` and **NOT**
`sale.external_id` (both of which carry the ORIGINAL sale's id). Writing the original's id would
collide with the original SI's unique slot and be falsely treated as a dup-recovery, suppressing a
legitimate reversal.

This is enforced and tested in the **pure** layer (`reversal_builder.py` overwrites both provenance
fields after composing on the forward builder; `test_reversal_builder.py::TestF002ProvenanceIdentity`
asserts `rt_external_id == work_item.external_id` and `!= reversal_of.external_id` and
`!= sale.external_id`, using a fixture where all three differ). Reading from the top-level
`work_item.*` also matches what `frappe_glue._find_posted_invoice` queries by, keeping a future
reversal dup-recovery consistent. (Matches the forward-constraint note in `wave-status.md`.)

## Cardinality + idempotency

- Forward sale→SI is **1:1**. Reversal→original is **N:1** (successive partial returns share one
  `reversal_of`). Each reversal work-item carries its OWN `external_id`, so each yields a distinct
  `rt_external_id` — the forward 1:1 does not bleed in (tested:
  `TestCardinalityNto1`).
- Idempotency is **per reversal-request key**, reusing the SAME `store` replay primitive
  (`get_document_ref` / `record_posted`, keyed on the reversal work-item's own
  `(source_system, external_id)`) that the sale_post path uses — no new primitive introduced.

## The seam (architecture)

Mirrors the existing `builder.py` / `frappe_glue.py` split:

1. **Pure builder** — `reversal_builder.build_reversing_invoice(work_item, *, uom_for,
   warehouse_for, customer_for) -> dict`. No frappe. **Composes** on `build_sales_invoice` (one money
   path: `assert_money_conformance` validates the POSITIVE magnitudes once; no duplicated line loop,
   and `uom.py` is left untouched — its `_QUANTITY_RE` is unsigned). Then sets `is_return=1`, negates
   each line's `qty`+`amount` (rate stays positive — ERPNext return semantics), overwrites the two
   provenance fields (F-002), and overwrites `posting_date` with the reversal's OWN `business_date`
   (the credit note posts in its fiscal period, not the original sale snapshot's). Fully unit-tested
   locally — 15 tests pass.
2. **Thin bench leg** — `frappe_glue._post_reversal(...)` replaces the old F-001 guard's reversal
   case. Replay-guard → `build_reversing_invoice` → resolve original SI → insert/submit → record →
   ack, mirroring the sale_post path's transient/validation/dup/other handling.

## `return_against` — pure vs glue split

The pure builder **cannot** resolve `reversal_of` → the original SI's ERPNext docname (that needs a
DB hit; the injected signature has no SI-resolver). It emits a standalone `is_return=1` credit note
**without** `return_against` (ERPNext accepts that). The bench leg's `_resolve_original_invoice`
looks the original SI up by `(reversal_of.source_system, reversal_of.external_id, docstatus=1)` and
sets `return_against` before insert. If no submitted original SI exists, the reversal **fails closed**
(`permanently_rejected` / `validation`) — never post a reversal against a sale that was never posted
(Principle VI).

## G8 version posture

No contract/OpenAPI/YAML edited (SC-06): the 012 `posting-feed.yaml` is DP2-owned and consumed,
not changed. The `kind=reversal` enum, `ReversalRef`, and the top-level `externalId` already exist
in the 1.1.0-draft contract and in `contracts.py`; this slice only adds an apply path for them. No
contract version bump is required or made by this slice.

## Bench-pending status of the apply leg

`frappe_glue.py` imports `frappe` and is **un-importable on this machine** (no Frappe bench;
standing-rules §6). `_post_reversal` / `_resolve_original_invoice` are written, ruff-clean, and
`py_compile`-clean, but **NOT executed and NOT claimed passing** — they are validated on the staging
ERPNext v15 bench (same precedent as the forward `post_work_item` and the G5/F-002 probes). A
bench probe for the reversal leg (analogous to `bench-g5-probe.py` / the F-002 probe) is the
follow-up to prove ERPNext acceptance of the `is_return=1` + `return_against` document; it is NOT in
this slice (SC-11 — no frappe mock/harness is built to force it green locally).

## Residual / follow-ups

- Bench probe for `_post_reversal` (ERPNext acceptance of the credit note + `return_against`) —
  follow-up, not this slice.
- The same crash-between-`insert()`-and-`submit()` draft residual noted for the forward path
  (`wave-status.md`) applies to the reversal leg too; not newly introduced here.
- If reconciliation later needs to disambiguate forward vs return rows under the same logical sale,
  consider an `is_return` discriminator on the unique index (noted in `wave-status.md`). Not needed
  for this slice since each reversal carries a distinct `external_id`.
