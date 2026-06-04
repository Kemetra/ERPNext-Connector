# Wave Status — `003-data-pulse-auth-and-api-policy`

> Human-readable summary of where the spec stands. Mirrors and condenses
> `execution-map.yaml`. Maestro updates both together when a slice lands.

**Last updated:** `2026-06-04` by `maestro`
**Spec:** `003-data-pulse-auth-and-api-policy` (`specs/003-data-pulse-auth-and-api-policy/`)
**Base:** `origin/main` at `42d7a89` (Agent OS merged)
**Active finding(s):** `0` — see [Active findings](#active-findings)

---

## TL;DR

Spec 003 planning chain (spec → clarify → plan → tasks) is committed on the feature branch
and the Agent OS execution map is seeded with 6 docs slices. **Implementation has not
started** — paused before implement per the user. Two slices are `ready`
(`POLICY_SKELETON`, `TOKEN_SCOPE_DEPENDENCY`); the rest are dependency-blocked on them.
All slices are docs-only (no gated surfaces). Next move: dispatch `POLICY_SKELETON`.

---

## Merged on `main`

| Slice ID | Subject | Commit / PR |
|---|---|---|
| _None — implementation not started._ | | |

(The spec/plan/tasks planning artifacts are committed on the feature branch
`003-data-pulse-auth-and-api-policy`, not yet PR'd.)

---

## Local only — committed/uncommitted, not on `main`

| Slice ID | Branch | Commit | Notes |
|---|---|---|---|
| (planning artifacts) | `003-data-pulse-auth-and-api-policy` | spec/plan/tasks commits | spec→tasks committed; no implementation slices run yet |

---

## Active findings

_None._

---

## Blocked

| Slice ID | Blocked by | Notes |
|---|---|---|
| `AUTH_DIRECTION_AND_MODEL` | `POLICY_SKELETON`, `TOKEN_SCOPE_DEPENDENCY` | needs skeleton + token-scope dependency recorded first |
| `IDEMPOTENCY_AND_TAXONOMY` | `AUTH_DIRECTION_AND_MODEL` | same policy file; auth defined before idempotency |
| `SECRETS_AND_CORRELATION` | `AUTH_DIRECTION_AND_MODEL` | same policy file; token defined before its storage rules |
| `POLISH_AND_VERIFY` | `IDEMPOTENCY_AND_TAXONOMY`, `SECRETS_AND_CORRELATION` | citation verify + README + quickstart after all sections |

---

## Ready / approved — next to dispatch

| Slice ID | Type | Agent | Approval needed? | Notes |
|---|---|---|---|---|
| `POLICY_SKELETON` | docs | docs-mapping | no | skeleton + Sources & precedence (T001–T002) |
| `TOKEN_SCOPE_DEPENDENCY` | docs | docs-mapping | no | DP2 connector-token-scope decision record (T003); separate file, parallel-safe |

---

## Proposed (awaiting approval)

_None._ (No parallel groups proposed; the policy-file slices serialize.)

---

## Next recommended action

Dispatch `POLICY_SKELETON` (the MVP path's first slice). `TOKEN_SCOPE_DEPENDENCY` is also
ready and edits a separate file, so the two could run as a parallel pair if the user approves
a wave — otherwise run `POLICY_SKELETON` first, then `TOKEN_SCOPE_DEPENDENCY`, then the
blocked auth/idempotency/secrets slices unblock in order.

**Note:** SC-001 (staging authentication) is deferred — it needs a staging environment AND
Data-Pulse-2 to provision a connector token scope (the `TOKEN_SCOPE_DEPENDENCY` decision).

---

## Post-merge closeout

> When a PR for one of this spec's slices merges to `main`, run the closeout to refresh both
> this file and `execution-map.yaml`. Full workflow: `docs/agent-os/maestro-playbook.md`
> "Workflow — post-merge closeout".

Short prompt:

```text
Use Agent OS.
Close out PR #<PR_NUMBER>.
Spec: specs/003-data-pulse-auth-and-api-policy
Expected slice: <EXPECTED_SLICE_ID>
Update execution-map.yaml and wave-status.md.
Stop before commit.
```

---

## Next short Maestro prompt

```text
Use Agent OS. Execute slice POLICY_SKELETON. Stop before commit.
```
