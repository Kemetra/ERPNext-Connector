# Synchronization — The ERPNext Connector

> The connector is the **only** component allowed to touch ERPNext. It pulls sale postings from
> Data-Pulse-2, resolves each line to a confirmed ERPNext Item, posts, and acks the outcome.
> It never forks ERPNext, copies its core, or exports catalog out of ERPNext.

<p align="center">
  <img src="../assets/architecture/retail-tower-sync-flow.svg" alt="Animated Retail Tower OS synchronization diagram, connector focus" width="100%"/>
</p>

```text
Data-Pulse-2  ──▶  Retail Tower ERPNext Connector  ──▶  ERPNext / Frappe
```

## The connector's direction: capture-UP (posting)

The concrete flow the connector owns is **capture-UP** — sale facts captured in Data-Pulse-2
rise into ERPNext as postings:

| Step | What happens |
|---|---|
| Pull | `connectorPullPostings` — GET the cursor feed of pending postings from Data-Pulse-2 |
| Resolve | Map each sale line's `tenantProductRef` to a confirmed ERPNext Item via DP2's `erpnext_item_map`; fail **closed** on unresolved product / unmapped UOM |
| Post | Create the ERPNext document |
| Ack | `connectorAckOutcome` — POST the outcome back (requires `Idempotency-Key`) |

```mermaid
sequenceDiagram
    autonumber
    participant DP2 as Data-Pulse-2
    participant CN as Connector
    participant ERP as ERPNext
    DP2->>CN: connectorPullPostings (GET cursor feed)
    CN->>CN: resolve tenantProductRef → ERPNext Item (erpnext_item_map)
    CN->>ERP: create posting
    ERP-->>CN: outcome
    CN->>DP2: connectorAckOutcome (POST, Idempotency-Key)
```

```mermaid
flowchart LR
    classDef hub  fill:#7c3aed,stroke:#c4b5fd,color:#fff;
    classDef conn fill:#b45309,stroke:#fbbf24,stroke-width:3px,color:#fff;
    classDef erp  fill:#0f766e,stroke:#5eead4,color:#fff;

    DP2["🛡️ Data-Pulse-2<br/><small>posting feed · contract boundary</small>"]:::hub
    CONN["🔌 ERPNext Connector<br/><small>Frappe app · item-map resolve · fail-closed</small>"]:::conn
    ERP["🏛️ ERPNext / Frappe<br/><small>system of record</small>"]:::erp

    DP2 -- "pull postings (cursor)" --> CONN
    CONN -- "create posting" --> ERP
    ERP -- "outcome" --> CONN
    CONN -- "ack (Idempotency-Key)" --> DP2
```

## Non-goals (explicitly out of scope)

- **No catalog/product export *out of* ERPNext** through this connector — that reverse direction
  is barred (constitution G4); the connector consumes DP2's item map, it does not re-derive it.
- No ERPNext fork · no ERPNext core copied in.
- No direct `POS-Pulse → ERPNext` or `Console → ERPNext`.
- Contract-first and upgrade-safe; Data-Pulse-2 stays the orchestration and contract boundary.

> The diagram above shows both program-level flow colours for family consistency; the
> connector's **own** current scope is the capture-UP posting path described here.

Program-wide view: the
[Retail-Tower-Orchestrator](https://github.com/ahmed-shaaban-94/Retail-Tower-Orchestrator)
control plane.

> Architecture is stable; this document does not assert feature/merge status. See `specs/**`
> and `CLAUDE.md` for the authoritative implementation state (much of the connector is
> spec/policy at this stage; connector code lands in spec 006).
