# 006 — Wave Status (first impl slice: pure-Python core)

Companion to [tasks.md](./tasks.md); the sign-off + status record T092 designates. Records what
the first implementation slice landed, what is authored-but-deferred, and the gate stops. This
slice implements the **pure-Python core only** — the frappe-coupled glue is authored but
bench-deferred, and the **three** forbidden-surface dependencies are hard-stopped pending
explicit approval.

## Sign-offs (T001–T003) — recorded

User-authorized for this slice (the "i authorize" instruction serves as the sign-off record):

- **T001 — apply-only item posture** (rider R2 / Q-CON-004): the connector applies the
  pre-resolved `erpnextItemRef`; performs NO resolution/lookup/reach-back/cache. **Enforced in
  code**: `builder.build_sales_invoice` has no item-resolver parameter (only `uom_for` +
  `warehouse_for`); `contracts.SaleLine.from_wire` raises `MissingErpnextItemRef` on an
  unresolved offered line. A test asserts no resolution hook exists.
- **T002 — interim SI-only mode** (rider R1): `builder` produces a submitted Sales Invoice payload
  only; **no Payment Entry / tender** field appears anywhere in the core.
- **T003 — typed outcomes only**: the connector emits `posted | failed_transient |
  permanently_rejected`; reconciliation/DLQ/repair is DP2-side (017), not implemented here.

## Landed — pure-Python core (TDD, local RED→GREEN, 62 tests, lint clean)

| Task | Module | Tests | Notes |
|---|---|---|---|
| T010 | `connector/posting/contracts.py` | `test_contracts.py` (15) | frozen 012 DTOs; `MissingErpnextItemRef`; closed `RejectionReason` set |
| T011 | `connector/posting/transport.py` | `test_transport.py` (7) | `HttpTransport` Protocol + `PostingFeedClient`; `request_id` correlation |
| T030/T033/T034 | `connector/posting/builder.py` | `test_builder.py` (10) | apply-only builder; money exact-decimal; `businessDate`→`posting_date` |
| T040 / T042* | `connector/posting/idempotency.py` | `test_idempotency.py` (6) | `IdempotencyStore` Protocol; replay key (sourceSystem,externalId). *T042 409-conflict is **design-validated against the in-memory fake**; the concrete conflict-detection is part of the deferred T020 adapter (the Protocol declares the "MUST raise" contract). |
| T050/T052 | `connector/posting/reasons.py` | `test_reasons.py` (13) | closed-set mapper (raises, never invents); secret-scrub |
| T070/T071/T072 | `connector/posting/uom.py` | `test_uom.py` (11) | Option-A UOM map (fail-closed); pre-resolved warehouse; money conformance |

**Verification (this machine):** `pytest` 70 passed; coverage 94–100% on each core module
(`frappe_glue.py` shows 0% — un-runnable locally, by design); `ruff` clean; `py_compile` clean.

## Code review (independent) — all 12 findings addressed

An independent review (3 CRITICAL, 4 HIGH, 5 MED/LOW) ran against this slice; every finding was
verified real and fixed:

- **Core (locally re-tested, RED→GREEN):** F-006 (`_DECIMAL_RE` → 4 fractional digits, matches
  012 `DecimalAmount`); F-007 (`build_sales_invoice` now self-validates money in-path via
  `assert_money_conformance`); F-008 (scrub regex now catches JSON/quoted secrets + `sk_`);
  F-011 (missing/empty feed cursor raises); F-012 (empty `Sale.lines` raises).
- **Glue (fixed-by-inspection; still ⏳ BENCH-VALIDATION):** F-001 (reversal work-item fails
  closed, never mis-posts a positive SI); F-003 (transient log scrubbed); F-004
  (`Idempotency-Key` on every ack, incl. reject/transient); F-005 (narrowed transient-exception
  set; all other errors → `permanently_rejected`/`other`, never infinite re-offer); F-010
  (same — exception taxonomy).
- **F-002 (PARTIAL — duplicate-invoice window NOT closed):** concurrent double-record is now
  handled (echo the recorded ref). But the **crash-between-submit-and-record** window remains
  open — a re-offer after such a crash would submit a second invoice. `IdempotencyConflict`
  does not catch this. The real fix is **ERPNext-side dedup** (a unique key on
  `(rt_source_system, rt_external_id)`), which needs the provenance custom fields **declared**
  (the deferred custom-field gate below) — or a pre-submit pending-record. **Gate G5
  (idempotency) is therefore NOT yet satisfied** by this slice; it is deferred to T020 + the
  custom-field declaration and bench-validated there.
- **F-009 (customer/company gap):** now documented in `builder.py` as an OPEN deferred bench
  dependency — the SI requires a `customer` the 012 work-item doesn't carry; the slice does NOT
  fabricate one (Principle VI). Must be resolved before T031 bench validation.

## Authored-but-deferred — frappe glue (⏳ BENCH-VALIDATION, NOT run, NOT claimed passing)

- **T031/T032/T041/T051/T090** → `connector/posting/frappe_glue.py` (`post_work_item` +
  `_log_signal`). The ONLY module importing `frappe`. It composes the core into the live flow
  (submit → ack; replay-echo; transient/permanent classification; observability). It is
  **syntactically valid** (`py_compile` passes) but **un-importable locally**
  (`ModuleNotFoundError: frappe`) — validated on a staging ERPNext v15 site, not here
  (standing-rules §6). **No success claim is made for these paths.**

## HARD STOP — forbidden-surface gates (NOT touched; await explicit per-surface approval)

**Three** gated surfaces, not two:

- **T020 — idempotency-store DocType JSON** (`*/doctype/**/*.json`, §3 forbidden + G3 migration).
  The core depends only on the `IdempotencyStore` **Protocol**; the concrete Frappe-DocType
  adapter is unwritten.
- **T093 — poller `scheduler_events` registration** in `hooks.py` (§3 forbidden + follow-up §1
  "not wired in this lane"). `hooks.py` is **unchanged**.
- **Provenance custom-field declaration** (newly surfaced). `builder.build_sales_invoice` emits
  `rt_source_system` / `rt_external_id` / `rt_sale_ref` on the Sales Invoice payload — **custom
  fields on a standard ERPNext DocType**. On a real bench, `frappe.get_doc({...}).insert()`
  **silently drops fields the DocType does not declare** — so without a declaration the audit
  linkage from the SI back to the DP2 sale (FR-012) is lost *invisibly* (a Principle VI hazard,
  not merely a bench TODO). Declaring them needs a **Custom Field fixture (registered via
  `hooks.py` `fixtures`) or a patch** — both §3 forbidden surfaces. This dependency is part of
  the same deferred bench/gated work as T020/T093 and must clear before the bench validation
  (T031) can claim audit-complete posting.

## Inherited execution dependencies (NOT connector work — block live e2e)

- **T100** — DP2 serving the live posting feed end-to-end (DP-015 *implementation*; only its
  planning chain has merged).
- **T101** — a staging ERPNext v15 bench (every ⏳ task above runs there).

**End-to-end is therefore NOT achievable on this machine** — it requires the DP2 live feed and a
staging bench. This slice delivers the verifiable, frappe-free core; the remainder is correctly
deferred behind the bench and the two forbidden-surface gates.
