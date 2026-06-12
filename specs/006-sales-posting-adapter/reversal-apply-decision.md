# Reversal-apply slice — decision & status (Arc A S1)

Branch: `feat/006-reversal-apply`. Scope: route 012 `kind=reversal` work-items to a reversing
ERPNext document. Touches ONLY the Connector repo's posting layer + its tests.

## UPDATE — Reversal re-key (Arc A S1.5, Connector #28, branch `feat/006-reversal-rekey`)

**Confirmed defect (#28).** The S1 reversal-apply keyed its replay-guard AND wrote `rt_external_id`
on the work-item's top-level `(source_system, external_id)`, ASSUMING that anchor is
per-reversal-distinct. It is NOT: **DP2 emits the ORIGINAL sale's `external_id` as the top-level
anchor on a reversal work-item** (per-reversal distinctness lives only in `source_ref_id`, which is
NOT on the wire — verified absent from `posting-feed.yaml` `PostingWorkItem`). Result: a reversal of
a posted sale hit the replay guard, which returned the ORIGINAL sale's invoice and acked `posted` —
no credit note, no exception, no DLQ. Silent mis-success.

**Decision (CHECKPOINT-2 — A-opt-2, connector-side).** Re-key reversals onto `work_item_ref`
(= 012 `PostingWorkItem.workItemRef`, the status-row id, required, already the ack identity — the
connector-side per-reversal-distinct value that IS on the wire). The forward `sale_post` key is
UNCHANGED: `(source_system, external_id)` (SC-11). No DP2/contract change (SC-04/SC-06): the wire is
consumed as-is; the fix is entirely connector-side.

**One discriminator, three consumers.** `idempotency.provenance_id(work_item)` is the single source
of truth: `external_id` for `sale_post`, `work_item_ref` for `reversal`. All three reversal-distinct
sites read it so the crash/dup-recovery path cannot drift back into #28:
1. Replay-guard key — `idempotency.key_for` = `(source_system, provenance_id)`.
2. Written provenance — `reversal_builder` sets `rt_external_id = provenance_id(work_item)`,
   `rt_source_system = work_item.source_system`.
3. Dup-recovery lookup — `frappe_glue._find_posted_invoice` queries
   `rt_external_id == provenance_id(work_item)` (kind-aware; forward recovery still uses
   `external_id`).

**Store.** Both key shapes are `tuple[str, str]` and coexist in one store without type confusion or
collision: a `sale_post` key `(source_system, external_id)` and a `reversal` key
`(source_system, work_item_ref)` for the same logical sale are distinct entries. The only theoretical
clash is a `work_item_ref` (a UUID) equal to some `external_id` under the same `source_system` —
negligible. No store code change required.

**Tests (TDD).** The S1 F-002 fixture gave the reversal a DISTINCT top-level `external_id` — a FALSE
wire shape that masked #28. Corrected to the REAL wire: reversal `external_id` == original sale's
(`POS-9001`), `work_item_ref` is the distinct discriminator. New/updated assertions in
`test_idempotency.py` (`TestKeyDerivation`) and `test_reversal_builder.py`
(`TestF002ProvenanceIdentity`, `TestCardinalityNto1`): reversal key distinct from the original
sale_post's key even with the SAME `external_id`; `rt_external_id == work_item_ref`; N:1 →
distinct keys + distinct `rt_external_id`; both key shapes coexist. Pure layer: **139 passing**
locally (was 134), ruff-clean.

**Bench-pending.** `frappe_glue._find_posted_invoice` and `_post_reversal` import `frappe` and are
un-importable here (standing-rules §6); the kind-aware `provenance_id` edits are made, py_compile- and
ruff-clean, but NOT executed — validated on the staging ERPNext v15 bench, same posture as the S1
apply leg.

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
