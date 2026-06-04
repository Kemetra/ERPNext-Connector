# Implementation Plan: DocType Mapping Reference

**Branch**: `002-doctype-mapping-reference` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-doctype-mapping-reference/spec.md`

## Summary

Produce a reviewed **mapping reference** that records how each ERPNext concept corresponds
to a Retail Tower concept as modeled in **Data-Pulse-2** (DP2), with owner-of-truth, a
status (Resolved / Decision needed / Deferred), and a citation to the authoritative DP2
source. The reference **cites** DP2's existing model — it does not re-derive it — and adds
connector-side decision records for ambiguous mappings. This is a documentation + decision
artifact only: no connector code, DocType, or mapping logic (constitution Principle VII).

## Technical Context

**Language/Version**: N/A — Markdown documentation artifact. (Future connector code is
Python/Frappe v15 per spec 001; not produced here.)

**Primary Dependencies**: Data-Pulse-2 backend repo (`C:\Users\user\Documents\GitHub\Data-Pulse-2`)
as the authoritative reference for the Retail Tower side of every mapping.

**Storage**: N/A — no data persisted by this feature.

**Testing**: Reviewer verification against acceptance scenarios (citations locate, statuses
present, decisions have sign-off lines). No automated tests for a docs artifact.

**Target Platform**: N/A (reference document under `docs/architecture/`).

**Project Type**: Documentation / decision reference (single project).

**Performance Goals**: N/A.

**Constraints**: Cite DP2, do not redefine (FR-003, Principle I); address ERPNext documents
only via generic `{doctype, name}` (FR-004, Principle II); concept altitude only, no
field-level mapping (FR-010); within DP2, code/contracts outrank prose (spec Assumptions).

**Scale/Scope**: One mapping matrix (≥9 concept rows) + a set of decision records for the
"Decision needed" rows. No data volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial evaluation (pre-design):**

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. Data-Pulse-2 is the only orchestration boundary | ✅ Pass | The reference *cites* DP2 as the authoritative source for the RT side (FR-003); it introduces no connector-owned definition of RT concepts and no new path bypassing DP2. |
| II. No ERPNext fork (connector stays thin) | ✅ Pass | Addresses ERPNext only via the generic `{doctype, name}` reference DP2 exposes (FR-004); no ERPNext field names or core copied. |
| III. Additive & upgrade-safe changes | ✅ Pass (N/A) | Adds documentation only; no schema, no migration. |
| IV. Idempotent mutations | ✅ Pass (N/A) | No mutations. |
| V. Observable failures | ✅ Pass (N/A) | No runtime behavior. |
| VI. Fiscal & stock truth is never hidden | ✅ Pass | Tax/fiscal and stock concepts are recorded with explicit Deferred status and owning spec (006/007), not silently omitted. |
| VII. Spec-driven, contract-first delivery | ✅ Pass | This is the mapping-reference spec itself; FR-008 forbids any mapping implementation; ambiguous mappings gate downstream specs via signed decisions (FR-005). |

**Result**: PASS — no violations. Complexity Tracking empty.

**Post-design re-evaluation (after Phase 1):** See [Post-Design Constitution Re-Check](#post-design-constitution-re-check).

## Project Structure

### Documentation (this feature)

```text
specs/002-doctype-mapping-reference/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — DP2 authoritative citations + the 3 status calls
├── data-model.md        # Phase 1 — Mapping Matrix, Decision Record, Product-Item entities
├── quickstart.md        # Phase 1 — how a reviewer uses/verifies the reference
├── spec.md              # Feature specification
└── checklists/
    └── requirements.md  # Spec quality checklist (16/16 pass)
```

*No `contracts/` directory: this feature defines no external interface of its own. The
connector↔DP2 interface contract already exists and is owned by DP2
(`packages/contracts/openapi/erpnext-connector/posting-feed.yaml`); this reference cites it.
Emitting a contract here would create a second source of truth (FR-003 / Principle I).*

### Source Code (repository root)

```text
docs/
└── architecture/
    ├── doctype-mapping-reference.md   # the mapping matrix (FR-001..FR-004, FR-007, FR-009)
    └── boundaries.md                  # (existing per README layout; referenced, not required)
docs/decisions/
├── mapping-uom.md                     # Decision needed: UOM (no DP2 master) — FR-005
├── mapping-customer.md                # Decision needed/Deferred: Customer (not in DP2) — FR-005
└── ...                                # one record per "Decision needed" row
```

**Structure Decision**: The mapping matrix lives at `docs/architecture/doctype-mapping-reference.md`
(matches the README "Suggested Initial Repository Structure"). Decision records live under
`docs/decisions/` (also per README). Both are Markdown; no code.

## Complexity Tracking

> No Constitution Check violations. No complexity to justify. (Section intentionally empty.)

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (data-model.md + quickstart.md; contracts/ skipped with reason):

- **Principle I (DP2 boundary)**: Confirmed — `data-model.md` defines the matrix as a
  *citation structure* keyed to DP2 sources; no RT concept is defined independently.
- **Principle II (no fork)**: Confirmed — the matrix's ERPNext addressing column uses only
  `{doctype, name}`; no field-level ERPNext names appear.
- **Principle VII (no implementation)**: Confirmed — artifacts are Markdown reference +
  decision records; no mapping code, and "Decision needed" rows gate specs 003–007.
- **Principle VI (no hidden truth)**: Confirmed — tax, stock, payment concepts each carry an
  explicit status + owning spec rather than being dropped.

**Result**: PASS (post-design). No new violations. Ready for `/speckit-tasks`.
