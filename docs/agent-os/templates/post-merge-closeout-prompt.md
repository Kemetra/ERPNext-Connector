# Post-Merge Closeout Prompt — Template

> Reusable short prompt to close out a merged PR. Maestro observes that the
> merge happened, updates the spec's `execution-map.yaml` and `wave-status.md`
> to match, and stops before commit. Full workflow definition:
> `docs/agent-os/maestro-playbook.md` "Workflow — post-merge closeout".

## The short prompt

```text
Use Agent OS.
Close out PR #<PR_NUMBER>.
Spec: <SPEC_PATH>
Expected slice: <EXPECTED_SLICE_ID>
Update execution-map.yaml and wave-status.md.
Stop before commit.
```

Replace the placeholders:

| Placeholder | Meaning | Example |
|---|---|---|
| `<PR_NUMBER>` | GitHub PR number that just merged. | `6` |
| `<SPEC_PATH>` | Spec directory whose docs need updating. | `specs/002-doctype-mapping-reference` |
| `<EXPECTED_SLICE_ID>` | Slice ID Maestro should mark `merged`. | `MAPPING_MATRIX_BUILD` |

## Concrete example

Closing out PR #6 (the spec-002 mapping-matrix slice):

```text
Use Agent OS.
Close out PR #6.
Spec: specs/002-doctype-mapping-reference
Expected slice: MAPPING_MATRIX_BUILD
Update execution-map.yaml and wave-status.md.
Stop before commit.
```

## What Maestro does in response

1. Verifies PR is merged via `gh pr view`. Stops if not.
2. Captures `mergeCommit.oid` and `mergedAt` as audit fields.
3. Reads the spec's `execution-map.yaml`, finds the slice by `id`.
4. Updates the slice: `status: merged`, sets `merged_in_pr`,
   `merged_at_commit`, `merged_at_date`; moves any `blocks:` to
   `previously_blocked:`.
5. If the slice is `resolved_by:` for a finding, updates the finding the same
   way: `resolved_by_pr`, `resolved_by_commit`, `resolved_at`; moves `blocks:`
   to `previously_blocked:`.
6. Walks the slice list and clears the merged slice from every other slice's
   `depends_on:`. Transitions any newly-unblocked slice from `blocked` to
   `ready`.
7. Updates `wave-status.md`: bumps `Last updated` and `Base`, moves the merged
   slice to `Merged on main`, moves any resolved finding to the audit trail,
   updates `Blocked` / `Ready` rows, recomputes `Next recommended action` and
   the `Next short Maestro prompt`.
8. Runs `git diff --check` and the forbidden-path scan from the standing rules.
9. Reports changed files, exact transitions, and the new next-prompt.
10. **Stops before commit** unless the prompt explicitly authorizes
    `commit` / `commit and push` / `open PR`.

## What Maestro does NOT do

- Does NOT merge the PR. The closeout is post-hoc; the user (or GitHub) merges first.
- Does NOT edit unrelated findings, slices, or blockers. One PR → one closeout →
  one spec's docs touched.
- Does NOT silently mark a slice `ready` just because one dependency cleared. It
  must have **no remaining unsatisfied dependencies**.
- Does NOT expand the slice's `allowed_files` footprint after the fact. If the
  merged PR's changed files do not match the slice's `allowed_files`, Maestro
  stops and asks.

## When the slice doesn't exist

If the spec's `execution-map.yaml` does not contain a slice with the expected
ID, Maestro stops and asks the user to either (a) add the slice retroactively
as a new map entry, or (b) name the correct slice ID. Closeouts must not invent
slice IDs.

## Commit conventions

When the user authorizes commit after the closeout:

- Commit subject: `docs(<spec-short>): refresh Agent OS execution map`
  (e.g. `docs(002): refresh Agent OS execution map`).
- One slice → one closeout commit. Do not bundle with unrelated docs edits.
- Stage by exact path —
  `git add specs/<spec>/execution-map.yaml specs/<spec>/wave-status.md`.
  Never `git add -A`.
