# Retail Tower ERPNext Connector — Agent OS v1 Standing Rules

> These rules apply to **every** agent action in this repo unless the user
> explicitly overrides them. They are not negotiable defaults — they are
> hard contracts. When an agent says "Use Agent OS", these rules load with
> the slice.
>
> **Agent OS layers ON TOP of the existing governance — it does not replace it.**
> The project **constitution** (`.specify/memory/constitution.md`, Principles
> I–VII) binds every slice. The **Spec-Kit** flow (`specs/NNN/{spec,plan,tasks}.md`)
> is the source of work; slices reference its task IDs. Where these rules and
> the constitution overlap, the constitution wins.

---

## 0. Constitution is supreme

Every slice MUST comply with `.specify/memory/constitution.md`:

- **I — Data-Pulse-2 is the only orchestration boundary.** Cite DP2; never
  re-derive its model. No path bypasses DP2.
- **II — No ERPNext fork.** Never copy ERPNext/Frappe core into the app;
  address ERPNext only via generic `{doctype, name}`.
- **III — Additive & upgrade-safe.** Migrations ship with rollback notes;
  version pinning is documented; staging-before-production.
- **IV — Idempotent mutations.** (Applies once mutation work begins, spec 006+.)
- **V — Observable failures.** Structured logs + correlation IDs (spec 003+).
- **VI — Fiscal & stock truth is never hidden.** Record uncertainty as explicit
  status, never silently omit.
- **VII — Spec-driven, contract-first.** No business mutation before the
  relevant contract spec is reviewed; ambiguous mappings gate downstream specs.

A slice that conflicts with a constitution principle is a hard stop — adjust
the slice, never dilute the principle (the constitution changes only via an
explicit, separate constitution update).

## 1. Branch hygiene

- **Always start from latest `origin/main`.** `git fetch origin && git pull --ff-only origin main`
  before creating any branch or worktree. If local `main` is dirty or cannot
  fast-forward, stop and report.
- **One worktree per slice.** Worktrees live under
  `C:\Users\user\Documents\GitHub\connector-<short-slug>`. Never reuse a
  worktree across unrelated slices.
- **Branch names match slice intent:** `feat/`, `fix/`, `test/`, `docs/`,
  `chore/`, `refactor/`, `perf/`, `ci/`. Include the spec ID or task ID when
  one applies (e.g. `docs/002-doctype-mapping-reference`).

## 2. Slice discipline

- **Small, reviewable slices.** One concern per branch. If a task brief lists
  more than ~3 logically related files, ask whether it should be split.
- **No combining unrelated work.** A docs slice does not also edit app code.
- **RED-then-GREEN where applicable.** Where a bug fix has a non-trivial proof,
  ship a failing test commit then a fix commit. (For this repo, test execution
  is a deferred staging step — see §6.)
- **Slices reference Spec-Kit task IDs.** A slice covering `tasks.md` task
  T012 may be named `T012` or carry it in `task_ids` (slice-schema.yaml).

## 3. Forbidden surfaces — gates required

Every slice's brief must list `allowed_files` and `forbidden_files`. By
default, the following are **forbidden** and require explicit `[GATED]`
approval in the slice brief (the user approves before any tool call):

- `.specify/**` — the constitution, Spec-Kit templates, and `.specify` config.
  **Highest sensitivity:** the constitution governs everything else.
- `retail_tower_erpnext_connector/hooks.py` — app metadata + hook registrations
  (a mutation hook here would breach Principle VII).
- `retail_tower_erpnext_connector/**/doctype/**/*.json` — DocType definitions
  (structural schema; `issingle`, fields, permissions).
- `pyproject.toml` — packaging + version pin (Principle III).
- `retail_tower_erpnext_connector/patches.txt` and any future migration/patch.
- `.github/**` — CI workflows (none exist yet; adding any is gated).
- **Merged spec artifacts** under `specs/NNN/{spec,plan,tasks,research,data-model,quickstart}.md`
  once their PR has merged — these are the reviewed record. Re-opening them is
  gated (a fresh slice or a constitution-style amendment, not a silent edit).

When a slice legitimately needs one of these, the brief lists the exact path
in `allowed_files` and the user has approved before any tool call.

## 4. Out-of-scope surfaces — never touch unless requested

From the README non-goals — **not active work**, never modified unless the
user explicitly asks:

- **Do not fork ERPNext** or copy ERPNext/Frappe core code into this repo.
- **POS-Pulse cashier UI** (separate repo — never implemented here).
- **Retail-Tower-Console backend logic** (separate repo).
- **Direct Frappe calls from POS-Pulse** (must flow through Data-Pulse-2).
- **The Data-Pulse-2 repo itself** — it is read-only reference for the Retail
  Tower side of mappings. Never edit DP2 from this repo.

If a brief implies touching one of these, stop and confirm before proceeding.

## 5. Git operations — never autonomous

- **Never `git add -A` or `git add .`.** Always stage by exact path. (`-A`
  has historically swept in secrets and untracked artifacts.)
- **Never commit, push, open a PR, or merge without explicit instruction.**
  Asking once for a session does not authorize a second commit. Asking for
  commit does not authorize push. Asking for push does not authorize PR.
- **Never `--no-verify`, `--no-gpg-sign`, or force-push to `main`.** If a hook
  fails, fix the underlying issue and create a new commit. (Force-push to a
  feature branch also requires explicit authorization — it rewrites remote
  history.)
- **Never amend a published commit.** Always make a new commit.
- **Commit subjects** follow `<type>: <description>` and end with the
  `Co-Authored-By` trailer per the repo's git convention.

## 6. Validation contract — no local bench

Every slice's brief includes a `validation` block. The agent runs the checks,
reports results verbatim, and **does not declare GREEN without empirical
evidence**.

**This machine has no local Frappe bench.** Validation therefore splits:

- **Local checks (run now):** `python -m py_compile`, JSON validity
  (`json.load`), TOML validity (`tomllib`), `ruff` if configured, the
  forbidden-path audit, `git diff --check`, and — for docs slices — DP2
  citation-locates-in-repo checks and acceptance-scenario review.
- **Bench-validation (deferred to a staging ERPNext v15 site):**
  `bench install-app`, `bench migrate`, `bench run-tests`. These are marked
  `⏳ BENCH-VALIDATION` in the slice and in `tasks.md`, NOT run locally, and
  NOT claimed as passing until executed on a real bench. (This is the pattern
  established in spec 001's tasks.md.)

Do not weaken a test or add a default-skip to make red turn green. If a check
cannot run locally, mark it deferred — never fake it.

## 7. Stop conditions

The agent stops and reports — does not silently work around — when:

- The working tree is dirty in unexpected ways (files outside `allowed_files`).
- A required input (file, helper, prior commit, DP2 citation path) does not exist.
- The slice brief implies touching a forbidden surface (§3) without a `[GATED]` allow.
- A slice would conflict with a constitution principle (§0).
- Validation produces a result that doesn't match the brief's `expected` field.
- A claimed predecessor (e.g. "builds on PR #X") is not actually merged/accessible.
- Anything in the prompt is ambiguous about whether a gate is open.

"Scope creep" — making the slice 20% larger to fix something tangential — is a
stop condition.

## 8. Reporting

End-of-slice reports always include:

- Worktree path and branch name
- Changed files (exact list, with line counts)
- Validation results (each command, pass/fail, key output; bench steps marked deferred)
- Forbidden-path check result (empty / list of violations)
- Confirmation that no commit/push/PR happened unless explicitly authorized
- Next recommended slice or next prompt the user can issue

## 9. Persistent context

- **Read `CLAUDE.md`** at session start (machine-specific context: Windows,
  miniforge3 Python, encoding rules; and the active Spec-Kit plan pointer).
- **Read `~/.claude/global-lessons.md`** when debugging — many problems are
  already solved there.
- **Read project memory** (`~/.claude-work/projects/<project>/memory/MEMORY.md`)
  — e.g. the Frappe-no-bench and DP2-citation-verification lessons.
- **Update memory** when you learn something durable. Use the `MEMORY.md`
  index; never write memory content into the index itself.

## 10. Maestro pattern

Long-running multi-slice work goes through a **Maestro** (Opus, orchestrator)
who:

1. Loads the spec's `execution-map.yaml` to know slice state.
2. Selects the next slice based on dependency graph + user instruction.
3. Dispatches the slice with the per-slice brief.
4. Updates the execution map and `wave-status.md` when the slice lands.

This makes prompts short: **"Use Agent OS. Execute slice X. Stop before commit."**
is enough because the slice ID resolves to the full brief in the execution map.
The Spec-Kit chain (specify → clarify → plan → tasks → analyze → implement)
remains the upstream source of slices; Agent OS orchestrates their execution.

## 11. Dynamic workflows — slice controllers only

Dynamic workflows (the `Workflow` tool and any multi-agent orchestration it
spawns) are constrained to act as **slice controllers** — they orchestrate one
slice, they do not become a parallel authority that bypasses these rules. By
default:

- **One ready slice per workflow** unless the user explicitly approves a wave.
- **No whole-spec runs by default.** Approving one slice does not authorize the next.
- **Subagents are read-only by default.** Editable subagents require explicit approval.
- **Exactly one implementation path may edit files.** Parallel editable agents
  are forbidden (they race on shared files/state).
- **`allowed_files` still binds.** A workflow does not widen a slice's file scope.
- **Forbidden surfaces (§3) and out-of-scope surfaces (§4) stay off-limits.**
  A workflow cannot self-grant a gate.
- **Stop-before-commit holds (§5).**
- **Maestro inspects the raw script before repeat use** — to confirm it honors
  slice scope, read-only default, single edit path, forbidden surfaces, and the
  stop boundary.

In short: a workflow is a way to *run a slice with fan-out*, not a way to
escape slice discipline.
