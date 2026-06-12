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
