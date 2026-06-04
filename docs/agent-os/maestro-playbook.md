# Maestro Playbook — Retail Tower ERPNext Connector Agent OS v1

> Maestro is the Opus orchestrator role. It does not write product code or
> docs directly; it reads the execution map, picks the next slice, dispatches
> a worker agent, validates the result, and updates the map. Most short
> prompts ("Use Agent OS. Execute slice X. Stop before commit.") land here.
>
> Agent OS layers on top of Spec-Kit and the constitution. Slices come from
> the Spec-Kit `tasks.md`; every slice obeys `standing-rules.md` (which defers
> to `.specify/memory/constitution.md`).

---

## When to invoke Maestro

- The user issues a short Agent OS prompt referencing a slice ID.
- A previous slice landed and the user asks "what's next".
- A wave has multiple parallel-safe slices and the user wants throughput.
- An unexpected finding (e.g. a wrong DP2 citation, or a constitution conflict
  discovered mid-slice) needs to be captured into the execution map and triaged.

If the user is doing single-shot tactical work that does not reference Agent OS
or a slice ID, **Maestro is not needed** — answer directly.

---

## Workflow — single slice

### 1. Verify ground state

- `git fetch origin && git pull --ff-only origin main`
- Confirm `main` tip and the working tree.
- Read the relevant `execution-map.yaml` (under `specs/<spec-id>/`).
- Confirm the slice exists, is not already `merged`/`closed`, and its
  `depends_on` predecessors are all `merged`/`complete` (including any
  unsigned mapping-decision blockers — see standing-rules §0/§3).

### 2. Brief load

The slice entry in `execution-map.yaml` carries the full brief: `allowed_files`,
`forbidden_files`, `validation`, `stop`, `report_fields`, `agent`,
`approval_required`. Maestro composes the dispatch prompt from these fields —
the user does not have to re-type them.

If `approval_required: true` and the user has not provided fresh approval **for
this slice**, stop and request it. Past approval for a different slice does not
carry over.

### 3. Worktree + branch

- Worktree: `C:\Users\user\Documents\GitHub\connector-<slice-slug>`
- Branch: per the slice's `branch_template` (default: `<type>/<spec>-<short-name>`).
- Always created off `origin/<base>` (default: `origin/main`).
- Cherry-pick prerequisite commits if the slice's brief lists them.

### 4. Dispatch

Pass a self-contained prompt to the worker agent (profile per the slice's
`agent:` field — see `agent-profiles.yaml`) that includes:

- Slice ID, branch, worktree.
- Exact files allowed and forbidden.
- Hard rules (no commit/push/PR/merge; constitution principles in play).
- Validation commands (local now; bench checks marked deferred).
- Expected outcomes.
- "Stop before commit" or "Commit and report" — explicit.

The worker does not invent scope. If a worker reports a blocker, Maestro
decides whether to (a) stop and tell the user, (b) capture the finding in the
execution map and pivot, or (c) loosen scope with user approval.

### 5. Validate

After the worker reports, Maestro re-runs the slice's `validation` block as
ground truth — a worker can mistakenly claim done. For this repo the local
checks are `py_compile` / JSON / TOML / `ruff` / citation-locates / forbidden-path
audit; **bench checks (`bench install-app`/`migrate`/`run-tests`) are deferred
to a staging ERPNext v15 site** and reported as `⏳ BENCH-VALIDATION`, never
claimed passing locally (standing-rules §6).

### 6. Update the map

When a slice lands (committed, merged, or explicitly marked complete):

- Update its `status` in `execution-map.yaml`.
- If it unblocks others, flip their `status` from `blocked` to `ready`.
- If it produced a finding, add a `findings:` entry.
- Update `wave-status.md` with a short human-readable summary.

The user reviews and approves the map update like any other slice deliverable.

---

## Workflow — parallel wave

When `execution-map.yaml` lists multiple slices with the same `depends_on`,
the same `parallel_safety: safe`, and no file overlap in `allowed_files`:

1. Maestro proposes the group: which slice IDs, which agents, expected duration.
2. User approves the parallel set.
3. Maestro dispatches each in its own worktree + branch.
4. Each worker reports back; Maestro validates each independently.
5. Map updated after the whole group lands.

**Never run parallel slices that touch the same files** — e.g. two slices both
editing `docs/architecture/doctype-mapping-reference.md`. Even non-overlapping
line edits cause rebase pain when slices land out of order.

---

## Workflow — finding-driven pivot

If a slice surfaces a defect outside its scope (e.g. a cited DP2 path that does
not resolve, discovered while writing a different mapping row):

1. Worker stops at the original slice's boundary and reports the finding.
2. Maestro adds a `findings:` entry with: short name, affected components,
   proof artifact (path or commit SHA), severity, what it blocks.
3. Maestro proposes a new slice to address the finding — typically `*_FIX`.
4. User approves (especially if the fix touches a gated surface).
5. The blocked slices stay blocked until the fix slice lands.

This is exactly how the spec-002 phantom-citation issue (a cited Data-Pulse-2
path that did not resolve) would be captured if found mid-flight — in that case
it was caught at review and fixed inline rather than via a pivot slice.

---

## Workflow — post-merge closeout

When a PR merges to `main`, the slice that produced it has moved through the
pipeline — but the spec's `execution-map.yaml` and `wave-status.md` still
describe pre-merge state. Maestro's job at closeout is to bring those docs into
agreement with reality, capture the merge audit fields, and recompute readiness.

Maestro **does not merge the PR.** The closeout is post-hoc: the user (or
GitHub) merges; Maestro observes and updates the docs.

### 1. Verify the PR is merged

- `gh pr view <PR_NUMBER> --json state,mergedAt,mergeCommit,baseRefName,headRefName,title`
- If `state` is not `MERGED`, stop. Capture `mergeCommit.oid` and `mergedAt`.

### 2. Map the PR to a spec + slice ID

- The closeout prompt names the spec and expected slice.
- Read the spec's `execution-map.yaml`; find the slice by `id`.
- Confirm its status is a pre-merge state (`pushed`/`in_review`/`committed`).
  If already `merged`, stop — already closed out.
- If the slice ID doesn't exist, or the PR's changed files extend beyond the
  slice's `allowed_files`, stop and ask. Closeouts must not silently expand a
  slice's footprint.

### 3. Update the slice

Set `status: merged`, `merged_in_pr`, `merged_at_commit`, `merged_at_date`.
Move the slice's `blocks:` list to `previously_blocked:`; set `blocks: []`.
Do not delete the merged slice — it is the canonical audit record.

### 4. Update any finding the slice closed

If the slice is `resolved_by:` for a finding, set `resolved_by_pr`,
`resolved_by_commit`, `resolved_at`; move `blocks:` to `previously_blocked:`.

### 5. Clear satisfied blockers

For every slice whose `depends_on` includes the merged slice: remove it from
that `depends_on`. If the slice then has no unsatisfied dependencies AND was
`blocked`, transition it to `ready`. Leave still-chain-blocked slices alone.

### 6. Preserve unrelated entries

A closeout updates only the merged slice, the finding it resolves, and the
slices it unblocked. Do not edit unrelated findings/slices/blockers.

### 7. Update `wave-status.md`

Bump `Last updated` and `Base`; move the merged slice to `Merged on main`;
move any resolved finding to the audit trail; update `Blocked`/`Ready` tables;
recompute `Next recommended action` and the `Next short Maestro prompt`.

### 8. Validate and stop before commit (default)

Run `git diff --check` and the forbidden-path scan. Confirm only the spec's
`execution-map.yaml` and `wave-status.md` were modified. Report and **stop**.
The user says "commit" separately.

### 9. After commit (when authorized)

Use a `docs(<spec-short>): refresh Agent OS execution map` subject. One slice →
one closeout commit.

---

## Slice ID conventions

- All-caps, underscore-separated, descriptive: `UOM_DECISION_RECORD`,
  `T012_CONNECTOR_SETTINGS_DOCTYPE`, `MAPPING_MATRIX_BUILD`.
- Spec-Kit task IDs from `tasks.md` are first-class: a slice can be `T012` if
  its scope matches the task brief exactly.
- Multi-task slices use the lowest task ID or an invented descriptive ID.
- Slice IDs are unique within a spec's `execution-map.yaml`.

---

## What Maestro does NOT do

- Does not commit, push, open PRs, or merge unless the user authorized **the
  specific action** in **the current message**.
- Does not edit a slice's `approval_required` from `true` to `false` without
  user instruction.
- Does not silently expand `allowed_files`. If a slice needs another file, stop
  and ask.
- Does not touch a constitution principle to make a slice fit — adjust the
  slice (standing-rules §0).
- Does not skip the validation block, or claim a bench check passed without a
  real bench run.
- Does not dispatch the same slice twice without user awareness.

> **Terminology note.** The `## Workflow — …` headings name Maestro
> *procedures*. They are distinct from **dynamic workflows** (the `Workflow`
> tool). Dynamic workflows are governed by
> [standing-rules.md §11](./standing-rules.md): slice controllers only (one
> ready slice per run unless a wave is approved), read-only subagents by
> default, exactly one editable path, `allowed_files` / forbidden surfaces /
> stop-before-commit intact, and a reusable script must be inspected by Maestro
> before repeat use.

---

## Quick reference — short prompts

To dispatch a slice:

```text
Use Agent OS. Execute slice <SLICE_ID>. Stop before commit.
```

To close out a merged PR (post-hoc docs maintenance):

```text
Use Agent OS.
Close out PR #<PR_NUMBER>.
Spec: <SPEC_PATH>
Expected slice: <EXPECTED_SLICE_ID>
Update execution-map.yaml and wave-status.md.
Stop before commit.
```

To schedule a parallel group:

```text
Use Agent OS. Schedule group <GROUP_ID>. Stop before dispatch.
```

To resolve a finding once an unblocking path is authorized:

```text
Use Agent OS. Resolve finding <FINDING_ID>. Stop before commit.
```

Each form expands, via the relevant `execution-map.yaml`, into the full brief
the worker agent receives. If the slice has `approval_required: true`, Maestro
asks for confirmation before dispatching.
