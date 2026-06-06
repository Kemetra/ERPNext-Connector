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

## Poller activation + F-009 closure — code slice (2026-06-06, branch `feat/con-006-poller-activation-f009`)

The connector moves from "harness-validated machinery" toward "runs on the cron": the customer
source is closed (F-009) and the poller's config stubs are wired to read Connector Settings.

**F-009 — customer source CLOSED (build side, locally TDD'd):** the gate was a repo fact, verified
not assumed — `contracts.Sale` carries `store_id` (+ `source_system`), the only operator-mappable
identifiers; the 012 work-item carries no customer. So the customer is a **store→Customer map**,
exactly parallel to the existing store→warehouse map. `build_sales_invoice` gains a REQUIRED
`customer_for(store_id)->str` resolver (required, not optional-with-default — a default would let a
caller silently reintroduce F-009); `uom.StoreCustomerMap` resolves it and **fails closed**
(`UnmappedStore` → `permanently_rejected`/`validation`) — the connector NEVER fabricates a customer
(Principle VI). `frappe_glue` propagates `customers` and catches `UnmappedStore` in the existing
validation-reject branch. RED→GREEN locally: builder + StoreCustomerMap + the config parsers (below);
**108 passed**, ruff lint clean.

**Poller config wiring (the module is no longer inert):** `poller._build_http_transport` /
`_load_uom_map` / `_load_warehouse_map` / `_load_store_customer_map` now read **Connector Settings**.
The pure parse logic is split into `connector/posting/config.py` (`parse_uom_map` /
`parse_warehouse_map` / `parse_store_customer_map`) — frappe-free, unit-tested locally (empty rows,
half-filled rows → `ConfigError` fail-loud, duplicate keys → `ConfigError`), paying down the
test-infra debt for THIS slice's own code. Only a thin frappe shell remains: one
`frappe.get_doc("Connector Settings")`, `.get_password("dp2_token")` (Gate G4 — NOT
`get_single_value`, which masks a Password), and `cfg.parse_*(doc.<child_table>)` (child rows are
not in `tabSingles`, so they must be read via the doc object). A missing base-URL/token raises →
`run_posting_poll()` skips the tick cleanly (logged `posting.poll.skipped`), never posting blind.

**[GATED] §3 surfaces — user-approved for this slice.** "finish what remains … i authorize"
authorizes the gated surfaces this activation REQUIRES (the poller is *designed* inert until they
land — declined in prior sessions, now in scope). Recorded explicitly per standing-rules §3:
- **`connector_settings/connector_settings.json`** — extended from placeholder to: `dp2_base_url`
  (Data), `dp2_token` (**Password**, Gate G4 — stored encrypted, read via `get_password`, never
  logged), and three Table fields (`uom_map`/`warehouse_map`/`store_customer_map`).
- **Three new child DocTypes** (`rt_uom_map_row`, `rt_warehouse_map_row`, `rt_store_customer_map_row`)
  — JSON + `__init__.py` + a `Document`-subclass controller `.py` each (required, or
  `frappe.get_doc("Connector Settings")` fails on `get_controller` import at the bench). Child
  fieldnames cross-checked to match the `config.py` parsers exactly (a mismatch → silent blanks →
  `ConfigError`).

**Lint posture (surfaced, NOT silently resolved):** the repo's `pyproject.toml` sets
`[tool.ruff.format] indent-style = "tab"`, but **every committed file is spaces** (no file has ever
obeyed the tab config). This slice matches the committed convention (spaces) — `ruff format --check`
will flag these files, but it already flags the whole repo; that is a pre-existing config/convention
mismatch for the maintainer to resolve separately, not this slice's regression. `ruff check` (lint)
is clean.

**NOT YET PROVEN (this commit is the CODE slice; bench validation is the next step):** the
end-to-end `run_posting_poll()` with the harness customer-injection OFF — that is the real F-009
closure proof (1 SI, provenance lands, DP2 → `posted`, customer from Connector Settings not the
harness). **Known risk to check FIRST at bench time:** the builder drops `company` (bets ERPNext's
default company on a single-company site); the old harness injected BOTH customer AND company, so if
the bench has no default company set, submit fails — confirm a default company OR add a
`store_company_map` child table (trivial; `config._parse_pairs` already generalizes) before running.

## Gate G5 / F-002 — crash-window exactly-once CLOSED (2026-06-06, bench-validated RED→GREEN)

The crash-between-submit-and-record window (F-002) is closed by a coordinated two-part fix, proven
on the configured bench with a three-state probe (`live-e2e/bench-f002-probe.py`):
1. **[GATED] Sales Invoice unique index** — `patches/sales_invoice_unique_provenance.py` adds
   `unique_rt_si_provenance` on `tabSales Invoice (rt_source_system, rt_external_id)` (MariaDB
   multi-NULL → manual SIs unaffected; only connector SIs deduped). User-approved gated surface.
2. **`frappe_glue` crash-recovery** — catch the dup-key on submit BEFORE the generic
   `frappe.ValidationError` (the index raises **`UniqueValidationError` ⊂ ValidationError** — CAPTURED
   on the bench via a diag probe, NOT guessed; ordering is load-bearing or a legit recovery would be
   FALSELY rejected) → `_find_posted_invoice((rt_source_system,rt_external_id,docstatus=1))` → back-fill
   the Posting Log → ack `posted` (echo), logged `posting.recovered`.

**Three-state bench proof:** no-index → **2 SIs** (RED, F-002 reproduced); index-only →
`UniqueValidationError` → would false-reject (proves part 2 necessary); index+catch → **1 SI, posted
echo** (GREEN). Regression: the normal posted-path + G5 replay-echo still pass with the index. Local
suite 89 passed.

**Honest scope of the closure (proven-vs-inferred):**
- **Regression guard is MANUAL.** The new glue paths (`_dup_provenance_exceptions`,
  `_find_posted_invoice`, the recovery branch) have NO automated test — `frappe_glue` is
  un-importable locally (the 89-pass suite never touches it) and the probe can't run under
  `bench run-tests`. Guarded only by the manual `bench-f002-probe.py` (same precedent as
  `bench-g5-probe.py`). "Closed" = closed + manually-probe-guarded, NOT CI-protected.
- **What the probe modeled:** a FULL completed post (incl. the first ack) then Posting-Log deletion —
  so the recovery re-ack hit DP2's 200-replay path. Duplicate-PREVENTION is proven for the post-submit
  window regardless. **Residual edge (narrower, NOT a regression):** a crash strictly between
  `insert()` and `submit()` leaves a `docstatus=0` DRAFT in the unique slot; a re-offer's dup-key then
  finds no `docstatus=1` SI → `_reject(OTHER)` + an orphan draft. Not closed here; logged as a known
  residual. The `docstatus=1` filter in `_find_posted_invoice` is CORRECT (never echo a draft) — do
  not "simplify" it away.
- **FORWARD CONSTRAINT for the reversal slice (012 kind=reversal, unbuilt):** an ERPNext credit note
  IS a Sales Invoice (`is_return=1`). The unique index spans ALL SIs, so the reversal builder MUST
  write the reversal work-item's OWN `external_id` into `rt_external_id` (the 012 work-item carries a
  distinct top-level `externalId`, separate from `reversalOf.externalId`) — NOT the original sale's —
  or it will collide with the original SI and be falsely treated as a dup-recovery. If linking to the
  original is needed, add an `is_return` discriminator to the index. Verify when building reversal.

## Live-flow Tier 2 — POSTED-path + Gate G5 VALIDATED end-to-end (2026-06-06)

The happy path is now proven against live systems (completing the live-flow story; reject-path was
PR #21). Setup: ran ERPNext `setup_complete` on the bench (Company "E2E Co" **abbr E2E** so the
auto-named `Stores - E2E` warehouse matches the harness; Standard CoA; Fiscal Year 2026; default UOM
`Nos`), then seeded masters — Customer "E2E Customer" (group Commercial / territory United States),
Item `TEST-ITEM-01` (stock UOM `Nos`). The harness `posted` mode injects customer/company AFTER
`build_sales_invoice` (harness-only; builder untouched) and drives `post_work_item` TWICE in-process
on the SAME work-item — the feed serves only `pending`, so G5 replay must be re-posted, not re-pulled.

**RESULT (verified at BOTH sources, not the harness print):**
- ERPNext: exactly ONE Sales Invoice `ACC-SINV-2026-00001`, **docstatus=1 (submitted)**, total 19.99,
  customer E2E Customer, **`rt_source_system=retail_tower_pos`** (the provenance custom fields LANDED
  on the SI — closes the F-009 audit-linkage concern that earlier sessions could only infer).
- DP2: row → `posted`, `document_ref={"doctype":"Sales Invoice","name":"ACC-SINV-2026-00001"}` —
  matches the ERPNext doc the connector posted.
- **G5 REPLAY-ECHO proven through the REAL flow:** the second in-process post hit the replay guard
  (`store.get_document_ref` → echo), posting NO duplicate (source SI count = 1); the replay ack also
  exercised DP2's 200 + `Idempotent-Replayed` path. This is live-flow proof, not just the isolated
  `FrappePostingLogStore` probe.

**SCOPE — what this does NOT prove (still open; do not read "posted-path validated" as "ready to post"):**
- **F-009 customer gap is NOT closed.** The connector's `build_sales_invoice` still emits NO
  customer/company; the SI only submitted because the HARNESS injected one. This proves the connector
  MACHINERY (build→submit→ack→replay) end-to-end, not that the connector can post in production. The
  customer-source design decision is still open.
- **F-002 (crash-window exactly-once) is NOT closed.** G5 here = replay-of-posted ECHO only. A crash
  BETWEEN `submit()` and `record_posted` would leave no Posting Log row → a re-offer submits a second
  SI. NOW FIXABLE: the provenance fields are declared + landing on the SI (proven this run), so the
  ERPNext-side unique key on `rt_external_id` that earlier sessions said was blocked is now possible —
  the natural next step to actually close G5.
- **`failed_transient`/retry-budget path** never exercised live (only reject + posted paths were).
- **Poller config stubs** (`poller.py` NotImplementedError) still unwired → the connector module is
  inert/unscheduled; this validation is harness-driven, not the scheduled poll.

## Live-flow Tier 2 — NO-SHIM reject-path e2e VALIDATED end-to-end (2026-06-06, after DP2 #508)

The DP2 contract bug (finding 1 below) was **fixed + merged** — Data-Pulse-2 PR #508 (RED→GREEN;
`projection.ts` now emits the 012 `{doctype:"Item",name}` object; 9 suites/59 tests green incl. the
served HTTP-edge). With #508 on DP2 `main`, the live e2e was **re-run with the harness shim REMOVED**:
DP2 `main` (api rebuilt) serves the object on the real wire (curl-confirmed
`{"doctype":"Item","name":"TEST-ITEM-01"}`); against a FRESH sale/posting row (clean idempotency key)
the connector pulled + **parsed DP2's real object wire with NO compensation** → built the SI → submit
failed (bare bench) → acked `permanently_rejected/validation` → **DP2 recorded it** (verified at
source: row `7c7c…` → `permanently_rejected/validation`). This closes the prior caveat ("the connector
parsed a SHIMMED payload, not DP2's real output") and PR #21's unchecked "re-run without the shim"
item. The single most important integration point is now validated against the real contract, no shim.
(An intermediate re-run on the OLD workItemRef hit a 409 from a session-stale idempotency key; the
connector's `worker.process_page` correctly ISOLATED it per the documented poison-pill fix — not a
defect, a contaminated re-seed; resolved by using a fresh sale.)

## Live-flow Tier 2 — reject-path e2e VALIDATED (2026-06-06, live DP2 main + WSL ERPNext bench)

The first true cross-system live round-trip ran end-to-end. Setup: WSL `.wslconfig` memory bump
(6.7→9.7 GiB; the bench was OOM-exit-137); DP2 015 feed/ack MERGED to `main` via **PR #505**
(api run as a pnpm process, dev Postgres/Redis healthy); a `pending` `sale_post` row direct-seeded
into `dp2-postgres-dev` (tenant→store→user→tenant_product→sale→sale_line→**confirmed** item-map
`TEST-ITEM-01`→**active** warehouse-map→pending posting-status) + a `connector`-scoped `auth_tokens`
row (raw token presented; server stores `sha256(raw)` bytea). Bench: `retail.localhost`, connector
app code re-synced from `main` (the bench copy was a STALE `docker cp` with the old
`/connector/postings` path — corrected to `/api/connector/v1/erpnext/postings`). The connector was
driven by a bench-console harness (`specs/006-.../live-e2e/drive_connector.py`) constructing
`PostingFeedClient` (real `requests` transport) + `FrappePostingLogStore` + `UomMap` +
`PreResolvedWarehouse` inline and calling `frappe_glue.post_work_item` — NOT the gated poller stubs
(user declined wiring the §3 Connector Settings DocType).

**RESULT (verified at the DP2 source, not the script's print):**
`erpnext_posting_status` for the work-item → `status=permanently_rejected`,
`rejection_category=validation`, `document_ref=NULL`. The full loop is exercised: DP2 serve →
connector pull (connectorBearer; 401 without token) → 012 parse → `build_sales_invoice` →
`frappe.get_doc().insert()/submit()` → `frappe.ValidationError` → `frappe_glue` maps to
`permanently_rejected/validation` → `connectorAckOutcome` → DP2 `applyRejected` recorded it.
Crucially the ack took the **real status-aware 201 path** (`_interpret_ack` saw an HTTP status),
closing the Tier-1 honesty gap (the `_interpret_ack` statusless path was test-only). Re-pull
confirms the feed no longer offers the ref.

**PROVEN vs INFERRED — the first exception was CAPTURED (not guessed):** a probe ran
`frappe.get_doc(built_doc).insert()` and printed the unscrubbed error. It is
**`frappe.exceptions.LinkValidationError: Could not find Row #1: UOM: Nos, Row #1: Warehouse:
Stores - E2E`** — the BARE-BENCH unsatisfied master links, NOT the F-009 customer/company wall (the
masters fail first, before any mandatory-customer check). `LinkValidationError` ⊂
`frappe.ValidationError`, so `frappe_glue:136` correctly mapped it to `validation`. **What this
proves:** the connector maps an ERPNext `ValidationError` → `permanently_rejected/validation` and
acks it over the live status-aware path. **What it does NOT prove:** the specific F-009 customer gap
(submit failed earlier on the missing UOM/Warehouse Items) — that needs the posted-path with a
configured bench. Earlier wording here ("missing customer/company") was inferred and is corrected.

**TWO findings from the live run:**
1. **DP2 015 contract bug (DP2-side, read-only here):** the feed serves `erpnextItemRef` as a BARE
   STRING (`projection.ts:40,171`), but the 012 `posting-feed.yaml` `ErpnextItemRef` is
   `type:object,required:[doctype,name]`. The connector is CORRECT (raised `AttributeError` on the
   real payload); DP2 violates its own contract. The connector's 28/28-passing unit tests + DP2's
   28/28 conformance both missed it (schema/fixtures in isolation, not the live projection) — the
   exact value of Tier-2. Compensated by a HARNESS-ONLY shim (wrap string→{doctype,name} at the
   transport boundary; connector `contracts.py` untouched, still fail-closes). **DP2 must fix on its
   015 feature.** (memory: dp2-erpnextitemref-contract-bug)
2. **Bench is a BARE ERPNext install** — 0 Company/Customer/Item/Warehouse/Fiscal-Year/UOM (setup
   wizard never ran). The reject-path proves the loop regardless; the **posted-path** needs full
   ERPNext company setup (Company + CoA + fiscal year) before a real SI can submit — assessed next.

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
