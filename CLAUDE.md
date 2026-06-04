# Retail Tower ERPNext Connector — Agent Context

Custom Frappe / ERPNext connector app integrating Retail Tower OS (via Data-Pulse-2)
with ERPNext. The Data-Pulse-2 repo is **read-only reference** for the Retail Tower side
of mappings — never edit it from here, never re-derive its model.

## Agent OS / Maestro operating mode

**GitHub is the source of truth. Chat memory is advisory.**

Short prompts expand from repo files, not from repeated user instructions. The prompt
`"Use Agent OS. Execute slice X. Stop before commit."` is complete — Maestro resolves the
full brief from the spec's execution map.

Bootstrap read order for every Agent OS session:

1. `git fetch origin && git pull --ff-only origin main` — always start from latest `origin/main`.
2. [.specify/memory/constitution.md](.specify/memory/constitution.md) — 7 Core Principles; supreme source of truth for all design constraints.
3. [docs/agent-os/standing-rules.md](docs/agent-os/standing-rules.md) — hard operating rules (constitution deference, branch hygiene, forbidden gates, no-local-bench validation, git discipline, stop conditions).
4. [docs/agent-os/maestro-playbook.md](docs/agent-os/maestro-playbook.md) — orchestration workflow (slice dispatch, parallel waves, post-merge closeout).
5. Active spec's `execution-map.yaml` (under `specs/<spec-id>/`) — slice state, allowed/forbidden files, validation contract.
6. Active spec's `wave-status.md` — human-readable progress, findings, next recommended action.
7. GitHub PRs / reviews — current authoritative state for in-flight work.

Agent OS layers ON the Spec-Kit flow (specify → clarify → plan → tasks → analyze →
implement) and the constitution — it does not replace them. Slices reference Spec-Kit
`tasks.md` task IDs. Do not duplicate standing-rules content here; `standing-rules.md`
governs when in doubt. Profiles: see [docs/agent-os/agent-profiles.yaml](docs/agent-os/agent-profiles.yaml).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/004-product-erpnext-item-mapping/plan.md`

Active feature: 004 Product–ERPNext Item Mapping (docs/policy only; **reframed** from the
README's "catalog export from ERPNext" — no such DP2 contract exists, reverse direction barred
by G4). The connector resolves a posting work-item sale line's `tenantProductRef` to a confirmed
ERPNext Item via DP2's `erpnext_item_map` (spec 013, migration 0017); CITES `erpnext-item-map.yaml`
+ `posting-feed.yaml`, does NOT export catalog or re-derive DP2. Spine = fail-closed unresolved
surfacing (Principle VI): unresolved product → `permanently_rejected`/`unmapped_item`, unmapped UOM
→ `validation`; ad-hoc line fails closed (signed). NO connector code — resolution lands in spec 006.
See `.specify/memory/constitution.md`.

Done: 001 Frappe App Foundation (implemented + validated), 002 DocType Mapping Reference
(merged), 003 Data-Pulse Auth & API Policy (merged). Their plans are under `specs/00{1,2,3}-*/plan.md`.

Data-Pulse-2 backend repo (authoritative reference, read-only):
`C:\Users\user\Documents\GitHub\Data-Pulse-2`.
<!-- SPECKIT END -->
