# 006 — Wave Status

Companion to [tasks.md](./tasks.md). Records what landed across the implementation slices.

## Live-flow Tier 1 — transport conformance (DONE, 2026-06-06, branch `feat/con-006-live-flow-tier1`)

Corrected the client/poller against the verified served contract (TDD; suite **89 passed**, ruff clean):
- **Served paths**: `transport.py` now uses `/api/connector/v1/erpnext/postings` (pull) +
  `.../{workItemRef}/outcome` (ack) — was the wrong `/connector/postings`, which would have 404'd
  every live call. Added the `limit` param (default 100, capped at 500); `since` sent verbatim.
- **Ack response semantics**: `ack_outcome` returns an `AckResult` — 201 (first) and 200 +
  `Idempotent-Replayed: true` (replay) are both success; **409 → `AckConflict`**, **404 →
  `AckNotFound`** (raised). Idempotency-Key `{workItemRef}:{outcome}` confirmed 16–128 ASCII / no ws.
- **Ack-failure isolation (the poison-pill fix)**: `worker.process_page` now CATCHES
  `AckConflict`/`AckNotFound` from a valid item's ack → records the ref in `ack_failed_refs` →
  marks the page degraded → **continues + advances the cursor** (DP2 owns reconciliation 017; the
  connector never blind-retries). Without this, a single 409 would wedge the poller forever
  (re-pull → replay → 409 → repeat) — the same poison-pill class as the degraded-page fix, caught
  by review before Tier 2 could trip it.
- **Cursor handling left UNCHANGED** — verified against DP2 `service.ts:218-224` that
  `since = result.cursor` + break-on-`next_page_token is None` is correct (not the bug I'd flagged).

**Tier-1 honest ceiling:** the ack failure *types + loop handling* are wired and unit-tested; the
`_interpret_ack` statusless path is a **test-only** success convenience — the real Tier-2 transport
must always carry status (note: `requests` exposes `.status_code`, the Protocol will adapt). Not yet
exercised against a live DP2 (Tier 2).

## Live-flow slice — scoped plan (2026-06-06)

DP2 shipped both feed operations on `main`: `connectorPullPostings` (PR #502, US1-FEED HTTP-edge +
`connectorBearer` auth) and `connectorAckOutcome` (PR #503, US2-ACK). T100 is substantially served.
The connector's live submit→ack flow is now possible. Verified contract (DP2 source, read-only):

- **Served paths:** pull `GET /api/connector/v1/erpnext/postings?since=<cursor>&limit=<≤500,def 100>`;
  ack `POST /api/connector/v1/erpnext/postings/{workItemRef}/outcome`. *(The connector's current
  `transport.py` hardcodes `/connector/postings` — must change to the real base path.)*
- **Auth:** `Authorization: Bearer <raw-token>`; an opaque revocable `auth_tokens` row with
  `scope='connector'`, tenant-scoped. **No issuance script** — the token is hand-inserted DP2-side.
- **Pull response:** `{items[], cursor, next_page_token}` (snake_case). `cursor` = last item's
  `sequence` on a non-empty page (echoes `since` on empty); `next_page_token` non-null **only when the
  page was full**. *(Verified `service.ts:218-224`: the connector's `since = result.cursor` +
  break-on-`next_page_token is None` is CORRECT — no re-baseline loop. Do not "fix" it.)*
- **Ack:** `Idempotency-Key` REQUIRED (16–128 printable-ASCII, no whitespace); **201** first record,
  **200 + `Idempotent-Replayed: true`** on replay, **409** body-drift/contradiction, **404**
  non-disclosing cross-tenant. *(The connector's client treats neither 201/200 specially nor checks
  the replay header — Tier-1 work.)*
- **Feed prerequisite:** a sale appears only after DP2's **worker** drains `erpnext.posting.requested`
  into a `pending erpnext_posting_status` row (needs a processed sale + confirmed item-map +
  warehouse-map). No worker → feed permanently empty.

### Tier 1 — transport conformance (DOABLE NOW, fake-transport-testable; no DP2/ERPNext/token)
Correct the client/poller against the verified contract, TDD like the existing 77 tests:
- real base path; `limit` param (≤500); send `since` verbatim (opaque numeric string, never int-parse).
- ack: accept 201 AND 200-replay as success; surface 409 (operator attention, not blind retry) + 404
  distinctly; confirm the `{workItemRef}:{outcome}` Idempotency-Key meets 16–128/charset.
- **No gated surface** (transport *logic*); the *config source* (base-URL/token from Connector
  Settings) is Tier 2 and DocType-gated.

### Tier 2 — live end-to-end (HEAVY, cross-system, partly NOT connector code — a runbook, not a promise)
Five prerequisites before one pull→post→ack runs: (1) DP2 up incl. the **worker**; (2) a connector
token **hand-inserted** into DP2 `auth_tokens` (DP2-side op, no script); (3) a processed sale +
confirmed item-map + warehouse-map → one `pending` row; (4) ERPNext seeded Customer/Item/Warehouse
(the F-009 wall) or `submit()` fails; (5) wiring the poller's `_build_http_transport`/`_load_*` to
read base-URL/**token (a secret → Connector Settings Password field, never logged, Gate G4)**/maps —
which **edits Connector Settings DocType JSON, a §3 gated surface**. This tier finally exercises the
G5 *replay path* and the glue (T031/T041/T051) that are currently inferred/deferred.

## Activation slice (2026-06-06) — all 3 gated surfaces, user-approved; Gate G5 bench-validated

The second implementation slice activated the posting module. The user explicitly approved all
three §3 forbidden surfaces (`hooks.py`, the `posting_log` DocType JSON + migration, the
custom-field fixture). Landed:

- **A — re-P2b worker loop** (`connector/posting/worker.py`, `transport.pull_postings_raw`): the
  ratified hybrid isolate-and-ack-then-raise-after. A feed line missing `erpnextItemRef` is acked
  `permanently_rejected`/`validation` per-item; valid items on the page still post; a
  `PageDegraded` alert is raised AFTER all per-item outcomes are recorded. No item is ever
  resolved/substituted. Local RED→GREEN (4 tests).
- **C — provenance custom fields** (`fixtures/custom_field.json` + `hooks.py` `fixtures`, scoped by
  name): `rt_source_system`/`rt_external_id`/`rt_sale_ref` declared on Sales Invoice — closes F-009
  (frappe no longer silently drops them). Bench-confirmed present.
- **B — `posting_log` DocType + migration + store adapter** (DocType JSON, `patches/posting_log_unique_idem.py`,
  `connector/posting/frappe_store.py`): a composite **UNIQUE index on `(source_system, external_id)`**.
  **This closes Gate G5** — exactly-once posting at the DB level.
- **D — poller** (`connector/posting/poller.py` + `hooks.py` `scheduler_events` cron): the scheduled
  pull→post→ack entrypoint (T093). Config-wiring stubs raise `NotImplementedError` so the poll
  **skips cleanly until bench-configured** (no half-configured posting). Module is now NON-dormant.

**Gate G5 — the dedup MECHANISM is bench-validated** on a real frappe v15 bench (WSL
`retail.localhost`, `bench migrate` + a runtime probe of `FrappePostingLogStore` in isolation),
not merely migrated. **Precise claim:** `record_posted`/`get_document_ref`/conflict/truncation are
exercised and pass; the *replay path through* `post_work_item` (replay_guard → echo existing
`documentRef`) is **inferred, not exercised** — it needs the DP2 client (T100). The probe caught and
the slice fixed **two runtime-only bugs** that migrate/import checks could not:

1. `frappe_store` caught `UniqueValidationError`, but a duplicate actually raises
   **`DuplicateEntryError`** on frappe v15 — the `except` caught the wrong exception (the race-path
   echo would have failed). Fixed: catch both (getattr-guarded), verified the dup-key path now
   raises `IdempotencyConflict` (echo the recorded ref, no duplicate document).
2. `external_id` was the default `varchar(140)` vs the 012 contract's **maxLength 200**, and the
   `format:` autoname made the primary key truncate too — two distinct long sale-ids would collide
   into a **false duplicate** (a valid sale silently rejected; Principle VI inversion). Fixed:
   `external_id` length 200, `source_system` 100, **autoname → `hash`** (dedup is purely the
   composite index). Bench-verified: two ids differing only past char 140 both record.

All 11 posting modules import cleanly under real frappe. Local suite **77 passed**, ruff clean.

The G5 probe is saved as a re-runnable bench script ([bench-g5-probe.py](./bench-g5-probe.py)) so
the validated behavior + the two fixed bugs have a durable regression guard (frappe's
`bench run-tests` cannot run it — see the test caveat below).

**Still deferred (NOT claimed validated):** the live submit→ack flow (poller config stubs +
seeded Customer/Item/Warehouse masters + DP2 serving the feed, T100). Codex-re-P2a
(closed_period/unmapped_account granularity) remains a bench-glue TODO.

### Codex review of #19 (commit `43666d8`) — 2 findings, both fixed + bench-verified

- **Codex-P1 (custom field length).** `rt_external_id` Custom Field on Sales Invoice was left at the
  default `varchar(140)` while `Posting Log.external_id` was fixed to 200 — the same truncation bug on
  the sibling field (a >140 externalId would truncate on the invoice → lost provenance / failed
  insert). Fixed: `rt_external_id` length 200, `rt_source_system` 100. Bench-confirmed the column
  synced.
- **Codex-P2 (scheduler-test flatten bug).** `test_scheduler_events_only_register_the_posting_poller`
  iterated `scheduler.values()` once over `{"cron": {expr: [job]}}`, so it collected the **cron
  expression** as a "job" and would fail on any real bench (`Unexpected scheduled job '*/5 * * * *'`).
  This is the concrete instance of the "never executed" caveat below. Fixed with a recursive
  `_flatten_scheduler_jobs` (str leaves only) — and this time the helper's logic was **executed on the
  bench** against the real hook shape: it returns the poller path, no cron-expr leaks.

**Test-execution caveat (honest):** `test_foundation.py` was edited to permit `scheduler_events`
(the poller) + add `test_scheduler_events_only_register_the_posting_poller`. That file is bench-only
and **`bench run-tests` aborts on collection** (`import pytest` in the posting tests; pytest isn't
in the bench container) — so the new foundation assertions have **not executed** anywhere. The
local pytest suite (77) does not import frappe, so it never runs `test_foundation.py` either. A
follow-up should make the connector tests runnable under one runner (install pytest in the bench, or
port the foundation/posting tests to unittest) so these guarantees actually execute.

---

## First impl slice — pure-Python core

This slice implemented the **pure-Python core only** — the frappe-coupled glue was authored but
bench-deferred, and the **three** forbidden-surface dependencies were hard-stopped pending
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

**Verification (this machine):** `pytest` 73 passed; coverage 94–100% on each core module
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

## Cross-model review (Codex, on PR #17) — 2 findings, both fixed

OpenAI Codex reviewed commit `ce377d5` on PR #17 and posted 2 findings on `frappe_glue.py`
(both verified real, fixed-by-inspection; glue stays ⏳ BENCH-VALIDATION):

- **Codex-P1 — per-outcome ack idempotency key.** The ack `Idempotency-Key` was keyed on the
  sale `(sourceSystem, externalId)` only, so a `failed_transient` ack and a later recovery
  `posted` ack on a re-offer reused the SAME key with DIFFERENT outcomes → `409
  idempotency_key_conflict` (resolution-concepts.md §4), making the recovery ack unreachable.
  **Fix:** `_ack_key(work_item, outcome)` = `{workItemRef}:{outcome}` — per-outcome, NOT
  per-attempt (a per-attempt nonce would break resend dedup). The two `posted` sites share a key
  (same logical outcome); transient and reject get their own.
- **Codex-P2 — `UnresolvedWarehouse` escaped the terminal-outcome invariant.** The build
  try-block caught only `(UnmappedUnit, MoneyConformanceError)`, so `warehouse_for` raising
  `UnresolvedWarehouse` (unknown store, rider R5) exited `post_work_item` with NO ack — violating
  SC-001 / Principle VI. **Fix:** catch `UnresolvedWarehouse` → `permanently_rejected`/`validation`,
  AND add a final `except Exception` → `other` on the build block so no build error escapes.

### Codex re-review (commit `dc75980`) — 2 further P2s, recorded, NOT fixed in this slice

A second Codex pass on the fix commit surfaced two deeper findings. Both verified real; neither
is fixed here (one is bench-coupled, the other is an open spec tension) — recorded as open items:

- **Codex-re-P2a — collapsed rejection categories (bench-deferred).** The `frappe.ValidationError`
  handler maps every submit-validation failure to `validation`, but ERPNext signals closed-period
  and unmapped-account as `ValidationError` subtypes too — so `closed_period` / `unmapped_account`
  (decision-table rows 4/6; the `reasons.py` vocabulary exists) collapse to `validation`, losing
  the distinction for DP2 017 reconciliation. **NOT fixed locally:** distinguishing them requires
  knowing which ERPNext exception class/message signals each — a **bench** fact, not safely guessed
  from memory. Same deferral bucket as T031/T051 (bench glue). Must be resolved at bench time.
- **Codex-re-P2b — batch-parse abort vs per-item ack (OPEN SPEC TENSION).** A feed page line
  missing `erpnextItemRef` makes `PostingWorkItem.from_wire` raise mid-parse (`transport.py`),
  aborting the whole page before any item is acked. Codex wants isolate-and-continue (ack the bad
  item, keep the good ones). **The spec itself says the opposite:** spec.md:233 and
  resolution-concepts.md:73 / row 8 both prescribe `permanently_rejected`/`validation` **AND
  STOP-and-raise** for this upstream-contract-violation case. The current code's abort-the-parse IS
  the STOP-and-raise the spec mandates. The two directives (per-item ack vs stop-and-raise) are in
  tension for a batch pull — this is an **unresolved spec question, not a code defect**; resolving
  it (graceful-degrade vs hard-stop) is a spec decision, not silently coded to Codex's reading.

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

## Bench import-check (2026-06-06) — modules load under real frappe; NOT 006 validation

A dev ERPNext v15 bench was found in WSL (`frappe_docker` devcontainers; site `retail.localhost`,
apps `frappe` + `erpnext` v15 + the connector). T101's "staging bench" is therefore **partly
satisfied** (it exists), though connector validation is not. The 006 posting code was copied into the
bench app copy (the bench has its OWN git lineage, disconnected from GitHub — a `docker cp`, not a
pull) and `bench migrate` ran clean (006 adds no DocType/patch). What this **did** and **did not**
establish:

- ✅ **All 7 posting modules import cleanly under real frappe** — including `frappe_glue.py` (the
  `import frappe` module the local host structurally cannot run). No import-time errors.
- ⚠️ **Finding — `_transient_exceptions()` names were partly guessed.** Under real frappe v15 it
  resolved to `['QueryTimeoutError', 'TimeoutError']`: frappe has `QueryTimeoutError` but **not**
  `TimedOutError` / `RetryBackoffError` (two names guessed from memory). The `getattr`-guard degraded
  gracefully (no bug), but the transient-exception set must be **pinned against real frappe v15** when
  the glue is properly tested (Codex-re-P2a is in the same area). Open TODO for the glue-test slice.
- ❌ **No 006 tests ran on the bench.** `bench run-tests` (unittest discovery) aborts on collection:
  the core tests are pytest-style and `pytest` is not installed in the bench container
  (`ModuleNotFoundError: No module named 'pytest'`). So the bench confirmed *imports*, not behavior.
- ❌ **The glue is still unvalidated and the module is dormant** (`hooks.py` empty — nothing executes
  it on the bench either). Real glue validation remains a **net-new slice**: glue tests (fake
  transport) + seeded `Customer`/`Item`/`Warehouse` fixtures (the F-009 wall) + DP2 for the live loop
  (T100). The bench existing makes that slice *runnable*; it does not shrink it.

**Accurate ceiling:** "the bench exists and the modules import under real frappe" — true and useful,
but it is **not** "006 is bench-validated." T031/T032/T041/T051 stay deferred to the glue-test +
fixture slice; the live loop stays deferred to DP2 (T100).
