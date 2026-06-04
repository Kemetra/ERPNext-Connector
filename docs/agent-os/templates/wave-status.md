# Wave Status — `<spec-id>`

> Human-readable summary of where the spec stands. Mirrors and condenses
> `execution-map.yaml`. Maestro updates both together when a slice lands.

**Last updated:** `<YYYY-MM-DD>` by `<author>`
**Spec:** `<spec-id>` (`specs/<spec-id>/`)
**Base:** `origin/main` at `<short-sha>`
**Active finding(s):** `<count>` — see [Active findings](#active-findings)

---

## TL;DR

One paragraph. What is done, what is blocked, what is the next move.

---

## Merged on `main`

| Slice ID | Subject | Commit / PR |
|---|---|---|
| `<T-NUM>` or `<SLICE_ID>` | `<short description>` | `<PR #>` or `<commit sha>` |

---

## Local only — committed/uncommitted, not on `main`

| Slice ID | Branch | Commit | Notes |
|---|---|---|---|
| `<SLICE_ID>` | `<branch>` | `<sha>` | `<why not merged yet>` |

If empty, write "_None._"

---

## Active findings

For each finding in `execution-map.yaml`, list:

### `<FINDING_ID>`

- **Summary:** one sentence
- **Affected:** `<components>`
- **Severity:** `<critical|high|medium|low>`
- **Proof:** `<commit sha or file path>`
- **Blocks:** `<slice ids>`
- **Resolved by:** `<slice id, if known>`

If empty, write "_None._"

---

## Blocked

| Slice ID | Blocked by | Notes |
|---|---|---|
| `<SLICE_ID>` | `<finding, slice id, or unsigned decision>` | `<one-line reason>` |

> Note: a slice may be blocked by an **unsigned mapping decision**
> (e.g. `docs/decisions/mapping-uom.md`), not only by another slice.

---

## Ready / approved — next to dispatch

| Slice ID | Type | Agent | Approval needed? | Notes |
|---|---|---|---|---|
| `<SLICE_ID>` | `<type>` | `<agent profile>` | `yes/no` | `<one-line>` |

---

## Proposed (awaiting approval)

Future slices that exist in the map as `status: proposed` — not yet authorized
for execution.

---

## Next recommended action

One paragraph. Which slice to run next, and why.

---

## Post-merge closeout

> When a PR for one of this spec's slices merges to `main`, run the closeout to
> refresh both this file and `execution-map.yaml`. Full workflow:
> `docs/agent-os/maestro-playbook.md` "Workflow — post-merge closeout".
> Reusable prompt: `docs/agent-os/templates/post-merge-closeout-prompt.md`.

Short prompt:

```text
Use Agent OS.
Close out PR #<PR_NUMBER>.
Spec: <SPEC_PATH>
Expected slice: <EXPECTED_SLICE_ID>
Update execution-map.yaml and wave-status.md.
Stop before commit.
```

The closeout updates these audit fields on the merged slice: `merged_in_pr`,
`merged_at_commit`, `merged_at_date`, `previously_blocked`. If the slice
resolves a finding, the same closeout sets `resolved_by_pr`,
`resolved_by_commit`, `resolved_at`, and `previously_blocked` on the finding.

---

## Next short Maestro prompt

```text
Use Agent OS. Execute slice <SLICE_ID>. Stop before commit.
```

Substitute the slice ID. If the slice is gated, the user will be asked to
confirm approval before dispatch.
