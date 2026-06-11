# Requirements Checklist — Draft D9+D10 Connector Admin Counterpart

> **DRAFT — NOT DISPATCHED.** Planning artifact under docs-only Orchestrator. No implementation, no contract, no migration, no gate mutation. Requires explicit scoped owner approval + G10 verification before any sibling-repo dispatch.

**Purpose:** Validate that this Connector-side follow-up draft is evidence-grounded, conforms to the shipped 018 boundary, and is free of forbidden side effects before it is used to plan any implementation.
**Created:** 2026-06-11
**Spec:** [../spec.md](../spec.md)
**Mode:** SPECIFY-ONLY (Orchestrator docs-only). **Owning repo (post-dispatch):** Retail-Tower-ERP-Next-Connector.
**Gating label:** gated — owner approval + G10 verification before dispatch.

> A checked box means the draft text already satisfies the item. Each cites the section/evidence that satisfies it. Owner-decision items point at the relevant open question.

## Scope & framing

- [x] **Single-node framing correct** — D9+D10 authored as ONE artifact set (kernel node `CON-018-COUNTERPART`); the `D9→D10` chain is recorded as REFUTED (co-gated siblings on shipped 018). *(spec header; §1; Dependencies.)*
- [x] **Conforms to a shipped boundary, does not re-specify it** — the DP-2 018 surface (contract + migration + guard) is cited as a shipped upstream dependency, not authored. *(§0 notes; N-2; E-1/E-3/E-4.)*
- [x] **Session-only correction applied** — the Connector is NOT the HTTP client of the admin surface; it consumes the issued credential (grounded in E-2). *(Clarifications Q1; §1; §4; N-3.)*
- [x] **Non-goals prevent scope creep** — N-1…N-8, including "no implementation," "no DP-2 file edit," "no admin-API client," "no posting-feed contract change." *(§3.)*
- [x] **Scope is clearly bounded** — SPECIFY-ONLY; current (E-5) vs target (§5/§6) vs open (OQ-n) kept distinct. *(header; Evidence basis; Open questions.)*

## Requirement quality

- [x] **No implementation masquerading as requirements** — schema/lifecycle described at spec altitude (Frappe DocType fields named as a *seam*, not code); implementation detail appears only as labeled current-runtime evidence (E-1…E-6). *(§5; §6; Evidence basis.)*
- [x] **Requirements are testable** — acceptance criteria A-1…A-8 are individually checkable; the cutover (§7) and lifecycle (§6) are concrete. *(§Acceptance; §6; §7.)*
- [x] **Dependencies & assumptions identified** — evidence table pins each repo's `origin/main` HEAD; gate + DAG dependencies enumerated. *(Evidence basis; Dependencies & sequencing.)*

## Journeys covered

- [x] **Service-credential lifecycle journey** — register → issue-linked → configure → active → expiry-warning → rotate / revoke / disable → 401-refusal. *(§6.)*
- [x] **Cutover journey** — backfill/register → issue linked credential → reconfigure → verify → revoke legacy, before US4 enforcement is live. *(§7; E-4.)*
- [x] **Operator-vs-admin separation** — human tenant-admin operates the session-only surface; the Connector machine consumes. *(§4; E-2.)*

## Security boundaries

- [x] **Raw secret discipline preserved** — secret stays a Frappe `Password` field, captured once (`IssuedCredential.secret`), never logged/surfaced. *(§5; §8 S-1; G-5; E-1.)*
- [x] **Lifecycle fields are non-secret** — registration/credential ids + timestamps are identifiers/status only (mirror DP-2's non-secret projections). *(§5; §8 S-2.)*
- [x] **Credential scopes not interchangeable** — `connector` scope only; authorizes no user/operator/device action; Connector rejects POS-originated calls. *(§8 S-3; 028 SR-10 / §15 CM-5.)*
- [x] **Least privilege + revocability + bounded expiry** — DP-2-revocable, atomically rotatable, bounded `expires_at`. *(§8 S-4; E-1.)*
- [x] **Opaque-bearer-as-v1; mTLS deferred** — inherits 028 §15 / OQ-10; no scheme rebuild. *(§8 S-5; N-6.)*

## Evidence discipline (the dispatch's runtime caution)

- [x] **Current runtime evidence reflected without assuming unverified work** — the reactive unlinked `dp2_token` is recorded as E-5 (verified on Connector `origin/main` `bc768ad`); not conflated with the target. *(Evidence basis E-5; §1.)*
- [x] **Shipped DP-2 surface cited, not assumed** — `connector-admin.yaml`, `0021`, and the US4 guard are cited from DP-2 `origin/main` (`0c57fed`/`6588e86`, PR #516) as E-1/E-3/E-4; the deferred consistency CHECK + runtime-only enforcement are stated faithfully (not "the DB enforces the link"). *(Evidence basis; §7.)*
- [x] **No unverified status claimed as fact (SC-09)** — every "shipped/closed" reference cites a file path / migration / operationId / PR; the Connector-side target is labeled DRAFT, not done. *(Evidence basis; banner; Acceptance A-6/A-8.)*
- [x] **Connector's own prior decision reconciled** — `connector-token-scope.md` Option-A "awaiting DP-2 delivery" closed by the shipped `connector` scope (E-6), recorded as a closure fact not a new claim. *(Evidence basis E-6.)*

## Provider / boundary independence

- [x] **Inherits 028 provider/boundary decisions** — `connector` scope, session-only admin boundary, opaque-bearer v1 all trace to 028 §15/§16 + OQ-10; no new boundary invented. *(§0 Relation-to-028; Clarifications; §8 S-5.)*

## DAG & gates

- [x] **G10 listed + gating label present on every file** — banner + "gated — owner approval + G10 verification" on spec, this checklist, plan, tasks. *(all four files' headers.)*
- [x] **G2 recorded as already-satisfied (consumed, not produced)** — conforms to shipped `connector-admin.yaml` + `posting-feed.yaml`; authors no OpenAPI. *(Dependencies; A-6.)*
- [x] **G3 scoped to the Frappe DocType delta only** — explicitly "DocType change via `bench migrate`, not SQL"; the only SQL migration (`0021`) is upstream. *(Clarifications Q3; §5; Dependencies.)*
- [x] **DAG edge recorded** — `CON-018-COUNTERPART depends_on [DP-018-IMPL]`; `D9→D10` REFUTED; fully parallel to the DP-2 spine. *(Dependencies & sequencing.)*

## Open questions

- [x] **Connector-specific OQs raised, not over-decided** — expiry-warning policy (OQ-1) and local-link-invariant (OQ-2) left open at plan altitude; the admin-API-client home (OQ-3) raised as a cross-repo routing decision, not decided here. *(Open questions.)*
- [x] **028 OQ-2/3/4/9/11 NOT auto-decided** — left open at the 028 boundary; not manufactured into Connector relevance. *(Open questions, carried-forward note.)*

## Forbidden-files / process compliance

- [x] **No forbidden files edited** — only the four spec artifacts now placed at `specs/007-connector-admin-counterpart/` were created (originally authored as the Orchestrator draft `d9-10-connector-admin`). No application code, Frappe DocType, migration, OpenAPI YAML, package/lock, CI, generated, secrets, env, or deployment file. No README/CLAUDE.md. *(authoring session.)*
- [x] **No sibling implementation-repo edit** — no file created or modified in Data-Pulse-2, POS-Pulse, Retail-Tower-Console, or Retail-Tower-ERP-Next-Connector. Sibling repos read **read-only** via `git show origin/main:` / `ls-tree` / `log` (SC-04/SC-05 honored). *(Evidence basis method.)*
- [x] **No git side effects** — nothing staged, committed, pushed, or PR'd; no `git add -A`/`git add .`; no branch switch; no checkout/pull/merge/reset/stash of any sibling repo.
- [x] **No gate/kernel/status mutation** — this draft does not advance the kernel queue, define a gate, or update status; it feeds a future Queue Item under G10 only. *(§0 notes.)*
- [x] **No secrets** — no raw token/key/password value anywhere; the once-shown secret is referenced by field name only, never reproduced. *(N-7; §5; §8.)*

## Notes / residual items (owner-facing, not blockers)

- **The admin-API client's home is genuinely open (OQ-3)** — the session-only contract (E-2) means a human-authenticated client must drive issue/rotate/revoke; most plausibly a Console follow-up (028 §20). This draft deliberately scopes only the Connector-side consumption + cutover; the client placement is an owner routing call.
- **G3 applies only because of the chosen lifecycle-aware design** — had the design been a bare secret-value swap, no Frappe schema delta (and no G3) would arise. The choice to record `expires_at` (for proactive warning, G-2) is what introduces the DocType delta. *(Clarifications Q4.)*
- **The cutover brushes rollout gates (G8/G9)** — §7 must complete before US4 enforcement is live; this is recorded as a rollout-coordination note, but per the brief the item's gate tags stay G10/G2/G3.
- **Not yet a kernel Queue Item** — adding a `CON-018-COUNTERPART` consuming task to `docs/kernel/graph.yml` with `gates: [G10, G2, G3]` is itself a named Orchestrator follow-up, to be done on owner approval, not in this SPECIFY-ONLY draft.
