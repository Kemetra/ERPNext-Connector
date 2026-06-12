# 007 — Wave Status

Companion to [tasks.md](./tasks.md). Records what landed across implementation slices for the
Connector Admin Counterpart (D9+D10 — registration-linked, rotatable service bearer).

## Slice 1 — T1+T2 codeable subset (2026-06-12, branch `feat/007-connector-admin-counterpart`)

The owner-approved (`"approved"` — Ahmed Shaaban, the named Decider) codeable subset of the 007
to-do list, authored TDD (RED→GREEN) off `origin/main` (`6b6f7e6`).

**Gate preconditions (T0) — verified, not assumed.**
- **Owner approval** — explicit `"approved"` this session clears the spec banner's owner-approval half.
- **G10 (Identity & Access Boundary Gate)** — verified against the reachable `Retail-Tower-Orchestrator`
  repo: `docs/gates/cross-repo-gates.md` records G10 evidence as *028 merged on main (PR #85 / `76cfcc3`)*;
  confirmed `76cfcc3` IS an ancestor of Orchestrator `origin/main`, and 028 §22 boundary decisions are
  present + signed (OQ-10 connector-bearer-as-v1 resolved). The residual OQs (2/3/4/9/11) are explicitly
  non-blocking. Both gate halves clear.

**T1 — configuration seam (D9), [G3 GATED — DocType delta).** `Connector Settings` extended
*additively* with four non-secret credential-lifecycle fields (spec §5):
`dp2_connector_registration_id` (Data), `dp2_credential_id` (Data), `dp2_credential_issued_at`
(Datetime), `dp2_credential_expires_at` (Datetime), under a new `credential_lifecycle_section`.
`dp2_token` stays a `Password` field (S-1 / Gate G4). `field_order` + `fields` kept consistent;
`modified` bumped. This is a Frappe DocType change applied by `bench migrate` — **not** SQL (the only
SQL migration in the chain, DP-2 `0021`, is upstream). **T1.2** is a Docker-free shape test
(`test_connector_settings_shape.py`, 8 tests) asserting the new fields/types and that **only**
`dp2_token` is a Password field.

**T2 — lifecycle-aware behavior (D9/G-2 + T2.2/003 §8).** New pure module
`connector/posting/credential_lifecycle.py` (frappe-free, injected-time pattern mirroring
`transport.py`):
- `evaluate_expiry(now, expires_at, warn_within, credential_id)` → `ACTIVE` / `EXPIRY_WARNING` /
  `EXPIRED` / `UNKNOWN`. The proactive pre-expiry warning (§6, G-2): compares `now()` to the recorded
  expiry and surfaces *"credential expiring — request rotation"* BEFORE a 401. `UNKNOWN` (no recorded
  expiry) is kept distinct from `ACTIVE` so a missing expiry never masquerades as healthy (Principle VI).
  The connector cannot self-rotate (admin surface session-only, N-5).
- `classify_auth_failure(operation)` → `AUTH_FAILED` re-auth state preserving **003 §8** exactly: surface
  re-authenticate, `retryable=False` (a 401 is a credential problem, not a transient — no blind retry),
  message carries the operation + a re-auth instruction and **never a token** (S-1/G-4) and stays
  non-disclosing (invents no cause the 401 body can't support). This reactive path COEXISTS with the
  proactive expiry path (§6 has two distinct 401 transitions — a credential revoked before expiry
  surfaces here while `evaluate_expiry` still reports ACTIVE).
- `apply_rotation(refs, new_credential_id, new_expires_at)` → swaps credential id + expiry, KEEPS the
  registration id (the stable identity that survives rotation, E-1/E-3); returns a new immutable
  `CredentialRefs`, never mutates the input.
- **T2.3** tests (`test_credential_lifecycle.py`, 12 tests): warning fires near/at the lead boundary,
  not when far; expired/unknown classified; 401 surfaces re-auth without token exposure and is
  non-disclosing + non-retryable; rotate keeps `registration_id`, doesn't mutate the input.

**Validation (local checks per standing-rules §6 — fresh evidence):**
- Full pure-Python suite **175 passed** (16 new: 8 shape + 8→12 lifecycle), excluding the bench-only
  `test_foundation.py` (imports `frappe`, un-runnable locally — pre-existing, not a regression).
- `ruff check` — All checks passed (the changed files).
- `py_compile` clean; `connector_settings.json` valid JSON.
- Secret discipline: only `dp2_token` is a `Password` field; no secret value in the diff.
- Forbidden-path audit (§3): the **only** forbidden surface touched is
  `connector_settings/connector_settings.json` — the owner-approved `[GATED]` T1.1 delta. No `hooks.py`,
  `patches.txt`, `pyproject.toml`, `.specify/`.
- `git diff --check` clean. **No commit/push/PR** (standing-rules §5 — awaiting explicit instruction).

**Changed files:** `connector_settings.json` (+37/−3); new `credential_lifecycle.py` (191),
`test_credential_lifecycle.py` (154), `test_connector_settings_shape.py` (94).

**Deferred (NOT done, NOT claimed) — carried forward, not regressions:**
- **T1.3** — `bench migrate` round-trip (idempotent/additive/backward-compatible) is `⏳ BENCH-VALIDATION`
  on a staging ERPNext v15 bench (no local bench, §6). The DocType is shape-tested locally; the migrate
  is not run here.
- **T3 (cutover, D10)** — register → issue-linked → reconfigure → verify → revoke-legacy. T3.1/T3.2/T3.5
  are **human tenant-admin** actions on the session-only 018 admin surface (E-2 — the connector never
  calls it); T3.4 is a live `connectorPullPostings`+`connectorAckOutcome` round-trip under the linked
  credential (live DP-2 + bench). Operational + rollout-coordinated, not agent-codeable here.
- **T4** — docs closeout (successor note to `data-pulse-auth-and-api-policy.md` §8 + `connector-token-scope.md`),
  post-dispatch owning-repo docs.
- **OQ-1/OQ-2/OQ-3** — pre-expiry warning lead time + channel (the helper takes `warn_within` as a param
  with a 14-day default, NOT silently hard-coded); local link-invariant; admin-API-client home — owner decisions.

**Next recommended step:** owner decides commit/PR for this slice; then T1.3 bench-migrate validation on a
staging bench, and OQ-1 (warning channel: operator UI banner / ops alert / posting-log) before wiring the
warning into the poller tick.

## Slice 2 — OQ-1 resolved + poller wiring (2026-06-12, branch `feat/007-oq1-expiry-warning`)

OQ-1 decided by the owner: **(a)** warn lead-time is **operator-configurable** (`dp2_credential_warn_days`,
default 14); **(b)** channel is a **structured ops-log event** (`posting.credential.expiring`), matching
`posting.poll.skipped` / `posting.feed.degraded`. Built TDD off PR #34's merged base.

- **OQ-1a parser (pure, locally tested):** `credential_lifecycle.parse_warn_within(warn_days)` →
  `timedelta`. Blank/`None`/`0` (unset Frappe Int) → `DEFAULT_WARN_WITHIN` (14d); negative/non-numeric →
  `ConfigError` (fail-loud, never a silent fallback that warns on the wrong schedule). 4 tests.
- **OQ-1a DocType field ([GATED]):** additive `dp2_credential_warn_days` (Int, default 14, non-secret) in
  the `credential_lifecycle_section`. Shape test extended (Int + default 14). `dp2_token` still the only
  Password field.
- **OQ-1b total composer (pure, locally tested):** `credential_lifecycle.build_expiry_warning(...)` →
  the log-payload dict or `None`. **TOTAL — never raises:** a malformed warn-days returns a
  `posting.credential.warn_check_failed` payload, so an advisory warning can NEVER abort a posting tick
  (best-effort). This keeps the branching + exception policy in the locally-testable layer (config.py
  discipline), not the frappe shell. 6 tests incl. the garbage-input → no-raise path and a no-token-leak
  assertion.
- **OQ-1b poller wiring (thin frappe shell, ⏳ BENCH-VALIDATION):** `poller._warn_if_credential_expiring`
  reads `dp2_credential_expires_at` / `dp2_credential_id` / `dp2_credential_warn_days`, calls the total
  helper with `frappe.utils.now_datetime()`, scrubs the detail, and logs. Called inside
  `_build_posting_path` (reuses the single `get_doc`, BEFORE the maps gate — warns even on a tick that
  later skips for unconfigured maps). The outer `try/except` guards only an irreducible frappe read
  failure. `poller.py` imports `frappe` → `py_compile` + ruff locally; behavior is bench-deferred (§6).

**Validation (local, fresh):** full pure-Python suite **186 passed** (11 new: 4 parser + 1 shape + 6
composer); ruff clean; `py_compile` clean (poller + lifecycle); `connector_settings.json` valid JSON;
only `dp2_token` is a Password field; forbidden-path audit — only the owner-approved `[GATED]`
`connector_settings.json`; `git diff --check` clean. **No commit/push/PR** until instructed (§5).

**Honest scope:** the OQ-1b *decision logic* is locally tested via the total `build_expiry_warning`; the
*poller shell* (field reads + `frappe.logger`) is inspection-only + `⏳ BENCH-VALIDATION` like the
sibling `_load_*` shells — its emit path runs on a real bench, not here.

**Changed files:** `connector_settings.json` (+8), `credential_lifecycle.py` (+69), `poller.py` (+37),
`test_credential_lifecycle.py` (+100), `test_connector_settings_shape.py` (+8).

## Slice 3 — OQ-2 resolved: local link-invariant (warn-only) (2026-06-12, branch `feat/007-oq2-link-invariant`)

OQ-2 decided by the owner: **adopt the local link-invariant as WARN-ONLY** (do not block). The DP-2 US4
guard refuses an unlinked `connector`-scoped token server-side (E-4); this surfaces the same condition
LOCALLY as an advisory. A hard skip was rejected because an unlinked legacy token still works until US4
enforcement reaches the connector's environment (E-5), and the D10 cutover legitimately has the token set
before the registration ref — a hard block would risk a self-inflicted outage on a working credential.
*(Recorded here, NOT by editing `spec.md`'s OQ-2 — merged spec artifacts are a §3 gated surface.)*

- **Pure helper (locally tested):** `credential_lifecycle.check_registration_link(token_present, registration_id)`
  → `posting.credential.unlinked` payload when a token is set but no registration ref is recorded
  (whitespace-only counts as empty), else `None`. **Total — never raises.** Takes only the token's
  PRESENCE (a bool), never the token value (S-1 / Gate G4). 6 tests (unlinked / None-reg / linked /
  no-token / whitespace / no-token-leak).
- **Poller wiring (thin shell, ⏳ BENCH-VALIDATION):** the existing expiry-warning shell was generalized
  and renamed `_warn_if_credential_expiring` → `_warn_credential_lifecycle`; it now runs BOTH advisory
  checks (OQ-1 expiry + OQ-2 link), passing `token_present = bool(get_password("dp2_token").strip())` —
  the bool, never the value. Both helpers are total, so the only thrower in the `try` is the frappe
  reads → caught → `warn_check_failed`; both payloads are then `_safe`-scrubbed and logged. Never blocks.
- **No gated surface this slice** — warn-only reuses existing fields; no DocType delta, no `hooks.py`.

**Validation (local, fresh):** full pure-Python suite **192 passed** (6 new); ruff clean; `py_compile`
clean (poller + lifecycle); forbidden-path audit — **none** (no gated surface touched); `git diff --check`
clean. **No commit/push/PR** until instructed (§5).

**Honest scope:** the OQ-2 *decision logic* is locally tested via the total `check_registration_link`; the
*poller emit path* (`frappe.logger`) is inspection-only + `⏳ BENCH-VALIDATION`, like the sibling shells.

**Changed files:** `credential_lifecycle.py` (+30), `poller.py` (+rename/+generalize), `test_credential_lifecycle.py` (+39).
