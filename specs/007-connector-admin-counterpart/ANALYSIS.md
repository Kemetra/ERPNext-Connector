# Readiness Analysis — Spec 007 Connector Admin Counterpart (D9+D10)

> **SPECIFY-ONLY / DRAFT — read-only analysis artifact.** This is the per-spec
> `/speckit-analyze` internal-consistency readiness pass (distinct from the cross-repo
> collision report). It cross-checks `spec.md` <-> `plan.md` <-> `tasks.md` for
> requirement->task coverage, consistency, and gate tagging. It authors **no** code,
> contract, migration, or gate mutation, and does **not** edit the existing spec files.
> Readiness != dispatch authorization: any dispatch still requires explicit scoped owner
> approval + G10 verification.

**Spec:** [./spec.md](./spec.md) - [Plan](./plan.md) - [Tasks](./tasks.md) - [Requirements checklist](./checklists/requirements.md)
**Kernel node:** `CON-018-COUNTERPART` (D9+D10 as ONE node) - **Gating label:** gated — owner approval + G10 verification before dispatch.
**Analysis date:** 2026-06-12 - **Analysis branch:** `docs/028-followups-analyze` (off `origin/main`) - **Mode:** internal readiness only.

---

## Method & scope

- Drove the `/speckit-analyze` detection passes manually. The repo's `.specify/` tooling exists,
  but `check-prerequisites.ps1` resolves `FEATURE_DIR` from the **git branch name**; the analysis
  branch (`docs/028-followups-analyze`) does not match the `007-` slug, so the script targeted a
  different spec. The analysis was therefore driven directly against the explicit
  `specs/007-connector-admin-counterpart/` path (the deliverable target). Detection-pass
  methodology (duplication / ambiguity / underspecification / constitution-alignment / coverage /
  inconsistency) is unchanged.
- **Identifier model for this spec.** There are no `FR-###`/`SC-###` keys. The buildable
  requirement surface is **Acceptance criteria A-1...A-8** and **Goals G-1...G-6**; the task surface is
  **T0.1-T0.3, T1.1-T1.3, T2.1-T2.3, T3.1-T3.5, T4.1, T-OQ1...T-OQ3**.
- **Read-only evidence confirmation (local only).** Confirmed the local D9 seam on
  `origin/main`: `retail_tower_erpnext_connector/connector/doctype/connector_settings/connector_settings.json`
  carries exactly `dp2_base_url` (Data) + `dp2_token` (Password) and **no** registration / credential /
  expiry fields — matching evidence **E-5** ("reactive, unlinked") faithfully. The DP-2-side evidence
  (E-1/E-3/E-4) was **not** re-verified here; that is the separate cross-repo pass. The repo
  constitution (`.specify/memory/constitution.md`, v1.0.1) was read for the alignment pass below.

---

## 1. Requirement -> task coverage matrix

Each acceptance criterion is classified: **(B)** buildable — must trace to >=1 task; **(I)** invariant /
negative — satisfied by a non-goal + "no change," no positive build task expected; **(P)** process /
gate-precondition.

| Req | Kind | Statement (abbrev.) | Covered by | Verdict |
|---|---|---|---|---|
| **A-1** | B | Config model carries registration ref + credential ref + bounded `expires_at` (Sec.5) | **T1.1** (additive DocType fields) - T1.2/T1.3 (shape test + bench round-trip) | Covered |
| **A-2** | B | Warn on impending expiry from recorded lifecycle, not only 401 (Sec.6, G-2) | **T2.1** (pre-expiry check) - T2.3 (warning-fires/-does-not unit tests) | Covered |
| **A-3** | B | Documented cutover register->issue->reconfigure->verify->revoke before US4 live (Sec.7) | **T3.1->T3.5** (full sequence) - T0.3 (US4 rollout timing) | Covered |
| **A-4** | I | 012 posting-feed runtime auth (`connectorBearer`, pull/ack) unchanged (G-4, N-4) | Invariant: N-4 + plan "Out of scope"; no task touches the feed contract -> correctly **no** positive task | Satisfied (invariant) |
| **A-5** | B | Connector never calls session-only admin surface; human admin operates it (E-2, N-3) | **T3.1/T3.2/T3.5** explicitly "(human tenant-admin)"; T3.3 is Connector-operator config only | Covered |
| **A-6** | I | No DP-2 file authored/modified; shipped 018 conformed to (N-2) | Invariant: N-2 + tasks legend "no task edits a DP-2 file"; T0.2 re-reads DP-2 read-only | Satisfied (invariant) |
| **A-7** | B | Raw-secret discipline preserved (Password field, never logged, captured once) (Sec.8 S-1, G-5) | **T3.2** ("never log/echo the secret") - **T2.2** (401 path never exposes token) - T1.1 (`dp2_token` stays Password) | Covered |
| **A-8** | I | No implementation/contract/migration/gate mutation in this draft (N-1) | Invariant: DRAFT banner on all files + tasks "NO CODE AUTHORED HERE"; tasks are post-dispatch instructions | Satisfied (invariant) |

**Goals coverage (cross-check, no double-counting):** G-1->T1.1 - G-2->T2.1/T2.3 - G-3->T3.x - G-4->invariant (N-4) -
G-5->T3.2/T1.1 - G-6 (scope non-interchangeability, Sec.8 S-3)->invariant inherited from 028 SR-10, no Connector build task (correctly so).

**Reverse direction — every task maps back:**

| Task(s) | Maps to | Note |
|---|---|---|
| T0.1-T0.3 | Gate preconditions (G10 verify, G2 re-read, US4 rollout timing) | **Process**, not an orphan — feeds A-3 timing + Dependencies sec. |
| T1.1-T1.3 | A-1 / G-1 | DocType seam. |
| T2.1-T2.3 | A-2 / G-2 (+A-7 via T2.2) | Lifecycle behavior. |
| T3.1-T3.5 | A-3 / A-5 (+A-7 via T3.2) | Cutover sequence. |
| T4.1 | Plan Phase 4 docs closeout | **Process/docs**, post-dispatch owning-repo docs — intentionally not an acceptance criterion. |
| T-OQ1-T-OQ3 | Open questions OQ-1/2/3 | Correctly carried as decisions, not pre-decided. |

**No buildable requirement is uncovered. No task is an unmapped orphan.** The two "process" task
groups (T0.x, T4.1) and the three OQ tasks are correctly non-acceptance-bearing.

---

## 2. Spec <-> plan <-> tasks consistency findings

| ID | Category | Severity | Location | Finding | Recommendation |
|---|---|---|---|---|---|
| C1 | Inconsistency (self-ref path) | LOW | `checklists/requirements.md` L66 | The forbidden-files item states the four files "were created" under `docs/specs/drafts/028-followups/d9-10-connector-admin/`, but they actually live at `specs/007-connector-admin-counterpart/`. Stale authoring-time path. | Owner: correct the self-reference in a future edit. Non-blocking; does not affect coverage or gates. **Not fixed here** (read-only; existing files untouched). |
| C2 | Gate provenance | LOW (note) | spec Dependencies; plan/tasks legends; constitution Sec.3 | The spec/plan/tasks lean on **G10 — Identity & Access Boundary Gate**, but this repo's constitution gate table defines **G1-G9 only**. G10 is the **Orchestrator's** cross-repo gate (`docs/gates/cross-repo-gates.md`), which the spec cites correctly. Gate set is mixed-provenance: **local G2/G3** (constitution Sec.3), **adjacent local G4** (Sec.8, noted not built), **cross-repo G10** (Orchestrator). | No action — internally consistent and correctly sourced. Recorded so a reviewer is not surprised that "G10" is absent from the local constitution. |
| C3 | Evidence note (cross-repo) | LOW (note) | spec Evidence basis table | DP-2 HEAD is listed as `6588e86` (badge) / `0c57fed` (substantive **#544**), while the shipped 018 surface is repeatedly cited as **PR #516**. The two PR numbers are reconcilable (badge/substantive vs the 018 delivery PR) but co-exist in the doc. | Cross-repo pass concern, not internal. T0.2 already mandates a dispatch-time re-read of DP-2 `origin/main` to re-confirm the HEADs — that control covers any drift. No internal-consistency defect. |
| C4 | Terminology | INFO | throughout | "credential" / "connector-scoped credential" / `connectorBearer` / `dp2_token` are used consistently with explicit role mapping in Sec.5 (table) and Sec.6 (state machine). No drift. | None. |
| C5 | Ordering | INFO | tasks T1->T2->T3->T4; Dependency notes | `D9->D10` is recorded as REFUTED (one node, no internal gate edge); the Sec.7/T3 order is explicitly labeled an *implementation* sequence, not a gate chain — and `(dep: ...)` annotations are internally consistent (T3.3 dep T1.3+T2.3+T3.2; T3.5 dep T3.4). No ordering contradiction. | None. |

**Duplication:** none found (D9 and D10 are deliberately one node; not a duplicated requirement).
**Ambiguity / placeholders:** none — no TODO/TKTK/`???`/`<placeholder>`; the only "soft" items are explicitly parked as OQ-1...OQ-3 with `T-OQ` tasks. Vague adjectives ("safe," "proactive") are each pinned to a concrete mechanism (cutover step order; `now()` vs `expires_at`).
**Underspecification:** none blocking — A-1...A-3/A-5/A-7 each have a concrete section-anchored mechanism and a task.

---

## 3. Constitution alignment (positive pass)

Validated against `.specify/memory/constitution.md` v1.0.1 (G1-G9 + Principles I-VII):

- **Principle VII (Spec-Driven, Contract-First)** — satisfied: the draft follows specify->plan->tasks
  and explicitly defers implement; uses `/speckit-analyze` + `/speckit-checklist` to de-risk, exactly
  as Sec.3 prescribes for high-stakes work.
- **Principle III (Additive & Upgrade-Safe; DocType changes ship rollback notes + pass G3)** —
  **directly validates** the spec's G3-on-the-DocType-delta tagging: T1.1 is additive, T1.3 records the
  bench-migrate round-trip as idempotent/additive/backward-compatible. The plan's claim that "G3
  applies to the Frappe DocType delta, not SQL" is constitution-conformant.
- **Principle V + Section 2 / Gate G4 (secrets never in logs/UI; revocable machine principal)** —
  validates S-1/G-5 and T2.2/T3.2: `dp2_token` stays a `Password` field, secret captured once, never
  echoed; the credential is bounded/revocable/rotatable.
- **Principles I & II (DP-2 is the only orchestration boundary; thin connector, no ERPNext fork)** —
  validates the framing that the Connector *consumes* the issued credential and never becomes an
  admin-API client (A-5/N-3), and that the change is a thin DocType+behavior delta.
- **Plan's "Principle VII" citation** — accurate (constitution lists exactly 7 principles; VII is the
  spec-driven one).

**No constitution MUST is violated.** No CRITICAL/HIGH constitution conflict.

---

## 4. Metrics

- Acceptance criteria: 8 (A-1...A-8) — buildable 5, invariant 3; **buildable coverage 5/5 = 100%**.
- Goals: 6 (G-1...G-6) — all traced (build or inherited-invariant).
- Tasks: 15 actionable (T0.1-T4.1) + 3 open-question tasks; **0 unmapped orphans**.
- Gate tags present: G10 (cross-repo, consumed/verify), G2 (local, satisfied), G3 (local, DocType delta), G4 (adjacent/noted).
- Findings: CRITICAL 0 - HIGH 0 - MEDIUM 0 - LOW 2 (C1, C2) + 1 cross-repo note (C3) - INFO 2.
- Ambiguity count 0 - Duplication count 0 - Constitution conflicts 0.

---

## 5. Dispatch-readiness verdict

### READY — internally complete and dispatch-ready, subject to G10 verification + scoped owner approval.

Basis:
- Every **buildable** acceptance criterion (A-1, A-2, A-3, A-5, A-7) traces to at least one concrete
  task; the three **invariant** criteria (A-4, A-6, A-8) are correctly satisfied by non-goals + "no
  change" with no spurious task.
- No contradiction, no duplication, no ambiguity/placeholder, no mis-tagged gate, no uncovered
  buildable requirement, no unmapped task.
- Gate tagging is internally consistent and correctly sourced (local G2/G3, adjacent local G4,
  cross-repo G10).
- Positive constitution alignment on Principles I/II/III/V/VII and Gate G4; no MUST violated.
- Scope discipline holds: SPECIFY-ONLY, no forbidden-file touch, no DP-2 authoring, secret discipline
  preserved.

**Non-blocking residuals to record (do not gate readiness):**
1. **C1 (LOW)** — stale self-referential path in `requirements.md` L66 (`docs/specs/drafts/...` vs actual
   `specs/007-...`). Owner to correct in a later edit; not fixed here (read-only scope).
2. **C2 (LOW note)** — "G10" is an Orchestrator cross-repo gate, absent from this repo's local G1-G9
   constitution table; correctly sourced from `cross-repo-gates.md`. Recorded for reviewer clarity.
3. **C3 (LOW, cross-repo)** — DP-2 evidence cites both #516 and #544 HEAD; reconcilable, and T0.2's
   dispatch-time DP-2 re-read covers any drift. Belongs to the cross-repo pass, not this internal one.

**Readiness != dispatch authorization.** Before any sibling-repo dispatch: G10 must be verified, 028 Sec.22
boundary decisions signed, and the owner must give scoped approval. All artifacts remain SPECIFY/DRAFT.

---

> **Docs-only record (SPECIFY-ONLY, DRAFT).** This analysis adds only `ANALYSIS.md` (and the companion
> `checklists/analyze-readiness.md`); it does not modify `spec.md`, `plan.md`, `tasks.md`, or
> `checklists/requirements.md`, and performs no git side effects.
