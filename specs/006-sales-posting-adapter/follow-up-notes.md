# 006 — Follow-up Notes (inherited gates, planned hooks.py scheduler_event, forward references)

Companion to [spec.md](./spec.md) and [resolution-concepts.md](./resolution-concepts.md). This
document records what spec 006 **inherits but does not satisfy**: the implementation gates, the
planned `hooks.py` registration (NOT done here), the Payment-Entry gated sub-scope, and the forward
references. Nothing here authorizes implementation — it sequences it.

---

## 1. Planned `hooks.py` `scheduler_event` — recorded, NOT wired (FR-014)

The connector pulls posting work-items from DP2 (`connectorPullPostings`); the runtime needs a
**poller**. Per the connector's foundation design, that poller will be the **first**
`scheduler_event` registered in `retail_tower_erpnext_connector/hooks.py` — which is **deliberately
empty** at the foundation layer:

> `hooks.py` lines 17–27 (spec 001 FR-005; constitution Principle VII):
> *"Foundation scope (spec 001): this app registers NO document-event handlers, NO scheduled jobs,
> and NO overrides… `doc_events`, `scheduler_events`, `override_doctype_class`, etc. are
> intentionally left unset at the foundation layer. They are introduced by later specs (003 auth,
> 004 product export, 005 inventory, **006 sales posting**) against their own reviewed contracts."*

**This planning slice does NOT edit `hooks.py`.** The registration is a *planned downstream
implementation task*:

- **Planned (not done)**: register a `scheduler_events` entry (e.g. a cron/`all`-interval job)
  that invokes the posting poller, which PULLs over `connectorPullPostings`, posts each work-item,
  and ACKs over `connectorAckOutcome`.
- **Gated by**: Principle VII (contract-first — this spec + its Spec-Kit chain reviewed first), the
  inherited gates in §2, and connector Gate G8 (the runtime ships through staging). The exact
  scheduler interval, the job's idempotency-store design, and the poller's cursor handling are
  **implementation concerns** for a later slice — not decided here.
- **Lock-scope note**: `hooks.py` is named in this slice's lock scope to *reserve* it against a
  conflicting dispatch, but the dispatch instruction is explicit — **no `hooks.py` edit in this
  lane**. Editing it is a separate, later, approved implementation slice.

---

## 2. Inherited implementation gates (NOT satisfied by this spec)

The connector posting runtime is **blocked** behind the rest of the DP-015 arc and the connector's
own gates. This spec records them; it satisfies none.

| Gate / prerequisite | Owner | What it is | Status for 006 |
|---|---|---|---|
| `P-DP-008-LIVELOOP` | Data-Pulse-2 | the 008 sale-capture live-loop (e2e prerequisite — separate slice, **not** absorbed into 015 per rider R6) | inherited blocker; owner-deferred |
| DP-014 warehouse mapping | Data-Pulse-2 | store→ERPNext-warehouse map; a missing map fails-to-DLQ before offer (rider R5) | inherited blocker |
| DP-015 Spec-Kit implementation chain | Data-Pulse-2 | 015's own `plan.md` → Constitution Check → `[GATED]` schema → `tasks.md` → `execution-map.yaml` | inherited blocker |
| `erpnext.posting.requested` event-type registration | Data-Pulse-2 (015 follow-up) | the DP2-side event/work-item production the poller consumes | upstream `[GATED]` follow-up |
| G5 — Idempotency gate | Connector | replay produces no duplicate ERP document | lands on the posting runtime |
| G7 — Observability gate | Connector | failures, retries, logs, correlation ids available | lands on the posting runtime |
| G8 — Upgrade gate | Connector | staging upgrade + regression checklist | lands on the posting runtime (and the `hooks.py` poller) |
| G9 — Pilot gate | Connector | one-branch pilot + rollback rehearsal | lands at pilot |

**012 contract correction/extension** (`P-DP-012-EXT`) is **DONE** — `posting-feed.yaml` already
carries the required `erpnextItemRef` (`1.1.0-draft`, DP-2 PR #494, merged 2026-06-05). It is the
one upstream prerequisite this planning slice depends on and it is satisfied; this is why the 006
*planning* gate (`Q-CON-004`) is cleared.

---

## 3. Payment Entry — the R1-gated sub-scope (forward reference)

The first implementation slice posts the **interim "submitted Sales Invoice / outstanding-AR only"**
mode (rider R1 — see [resolution-concepts.md §6](./resolution-concepts.md)). The Payment-Entry
sub-scope (the signed SI + PE target) is a **separate later slice** gated on:

1. a DP2 tender/payment fact model,
2. a 012 payment-carrying posting-feed extension (kept separate from the item-identity extension),
3. idempotent Payment-Entry creation in the connector,
4. payment repair/reconciliation semantics (the 017 boundary extended to payment outcomes).

Until those land, posting the interim mode is by design; deriving a Payment Entry from `posTotal`
is a **STOP-and-raise** (rider R1, "Not ratified").

---

## 4. Scope boundary of this slice (what was authored)

- **Authored** (planning/policy, docs-only): `spec.md`, `resolution-concepts.md`,
  `follow-up-notes.md` under `specs/006-sales-posting-adapter/`.
- **NOT authored** (out of this lane): `plan.md`, `tasks.md`, `data-model.md`, `execution-map.yaml`,
  any connector/Frappe code, any OpenAPI YAML, any migration, any `hooks.py` edit, any change to a
  README/status/queue doc.
- **Rationale**: this mirrors connector spec 004 and DP2's 011/012/013/015 spec PRs — a
  planning/policy spec carries companion docs but no dispatchable code slices; implementation
  derives separately behind the gates in §2 and the connector's own Spec-Kit chain
  (Principle VII).

---

## 5. Forward references

- [spec.md](./spec.md) — the 006 posting model, FRs, success criteria.
- [resolution-concepts.md](./resolution-concepts.md) — apply-only item identity, posting decision
  table, UOM/money, Payment-Entry gating.
- Connector spec 004 (`specs/004-product-erpnext-item-mapping/`) — rescoped by `Q-CON-004`; 006
  inherits its retained FR-002 + FR-008/US4 and not its retired FR-001/FR-003.
- Connector spec 003 decision (`docs/decisions/data-pulse-auth-and-api-policy.md`) — auth /
  idempotency / correlation / error / secrets substrate.
- Signed UOM decision (`docs/decisions/mapping-uom.md`) — Option A, input to FR-008.
- DP2 `specs/015-pos-sale-posting-to-erpnext/` + `specs/011-…/decisions/
  posting-decision-rider-2026-06-05.md` — the authoritative posting model + signed rider.
- 012 posting-feed contract (`Data-Pulse-2/packages/contracts/openapi/erpnext-connector/
  posting-feed.yaml`, `1.1.0-draft`) — the wire surface this adapter consumes.
