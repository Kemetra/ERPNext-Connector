# 006 — Resolution Concepts (apply-only item identity, posting decision table, UOM & money)

Companion to [spec.md](./spec.md). This document records the **rescoped** item-identity posture for
connector spec 006, the posting decision table, and the UOM / money posture — all grounded in the
read-only Data-Pulse-2 repository (`C:\Users\user\Documents\GitHub\Data-Pulse-2`). Every cited path
was verified to locate and confirm the claim (FR-013, Principle I).

> **Authority note.** The connector's earlier (004) framing had the connector *resolve* a sale
> line's `tenantProductRef` to an ERPNext Item. That framing is **retired** by the orchestrator
> decision `Q-CON-004` (rescope-with-supersession, ratified Wave-A 2026-06-05) and the **signed**
> DP2 rider `011-DR-POSTING-R1` R2. The connector now **APPLIES** a DP2-pre-resolved
> `erpnextItemRef`; it performs **no** resolution, lookup, reach-back, or caching.

---

## 1. The supersession: apply, never resolve (rider R2 / Q-CON-004)

**Signed source** — `Data-Pulse-2/specs/011-erpnext-pos-reference-and-integration-foundation/
decisions/posting-decision-rider-2026-06-05.md` (Decision ID `011-DR-POSTING-R1`, **SIGNED**),
section **R2 — ERPNext Item resolution side**:

> "Ratified: **DP2-side item resolution.** DP2 resolves each sale line's ERPNext Item reference at
> work-item projection time using the 013 `erpnext_item_map` (confirmed-only invariant). A sale
> line that cannot resolve to an ERPNext Item → the posting work-item **fails-to-DLQ in DP2 before
> being offered** to the Connector. **The Connector MUST NOT:** guess ERPNext Item identity; reach
> back into DP2 for item lookup; maintain a second copy of DP2 mapping truth."

**Contract realisation** — `Data-Pulse-2/packages/contracts/openapi/erpnext-connector/
posting-feed.yaml` (`version: "1.1.0-draft"`):

- `SaleLine.required` (line 459) **includes `erpnextItemRef`** — every offered line carries it.
- `SaleLine.erpnextItemRef` (lines 487–497): *"The DP2-resolved ERPNext Item identity for this line
  (REQUIRED). Resolved by Data-Pulse-2 at work-item projection from the confirmed 013
  `erpnext_item_map`; the connector APPLIES this pre-resolved reference and never looks up, infers,
  or stores item mappings (011 posting rider R2)."*
- `ErpnextItemRef` schema (lines 604–627): a `{doctype, name}` object, `doctype` const `"Item"`,
  `name` = the 013 `erpnext_item_ref` string (maxLength 140, opaque, version-independent O-6).
- `SaleLine.tenantProductRef` (lines 498–507): lineage-only, nullable for ad-hoc lines; *"The
  connector does NOT resolve this to an ERPNext Item — resolution is DP2-side (013), behind this
  contract."*

**What `Q-CON-004` retired vs retained** (orchestrator Wave-A ratification, 2026-06-05):

| Connector 004 element | Disposition under Q-CON-004 / rider R2 |
|---|---|
| 004 FR-001 (connector resolves `tenantProductRef` → confirmed Item) | **RETIRED** — resolution is DP2-side; connector applies `erpnextItemRef`. |
| 004 FR-003 (connector reads only `confirmed` mappings) | **RETIRED** — the confirmed-only invariant is enforced DP2-side at projection. |
| item-identity branch of 004 FR-006 / US3 | **RETIRED** — an unresolvable line fails-to-DLQ in DP2 *before* offer, so no offered line yields an item-resolution rejection. |
| 004 FR-002 (generic `{doctype, name}` addressing) | **RETAINED** — inherited as 006 FR-002. |
| 004 FR-005 (no item-search / no Item-creation / no auto-match source — `AUTO_MATCH_NO_SOURCE`, OQ-8) | **RETAINED / reinforced** — *not* a Q-CON-004 retirement; the prohibition still holds and is strengthened by moving resolution DP2-side. Inherited into 006 FR-003. |
| 004 FR-008 / US4 (UOM + money reconciliation) | **RETAINED** — inherited as 006 FR-008/FR-009. |

> **Ratified Q-CON-004 scope (verbatim):** retire **FR-001, FR-003, and the item-identity branch
> of FR-006/US3**; retain **FR-002 and FR-008/US4**. FR-005 is **not** in the retire set — it is
> retained and reinforced. This table aligns exactly to that record.

---

## 2. No substitute item, separate operational states (rider R3 / R4)

- **R3 — disabled / non-sales Item at posting time** (`posting-decision-rider-2026-06-05.md` §R3):
  *"A disabled / non-sales ERPNext Item at posting time fails-to-DLQ. **No silent fallback; no
  substitute item.**"* The connector therefore has **no "Misc"/catch-all Item** path — that is
  forbidden, not deferred. (This is the post-R3 reading of connector 004's earlier ad-hoc-line
  discussion: there is no catch-all Item, full stop.)
- **R4 — unknown-items ≠ unmapped-for-posting** (§R4): *"Resolving an unknown item creates a
  `tenant_product` that **still requires a confirmed 013 mapping** before it can post."* So an
  ad-hoc / unknown-item line never reaches the connector's feed without a confirmed mapping; the
  connector never improvises identity.

Consequence for the connector: an offered line **always** carries a resolved `erpnextItemRef`. If
the connector ever observes an offered line lacking it, that is an **upstream contract violation** —
fail-closed (`permanently_rejected` / `validation`) and **STOP-and-raise**, never substitute.

---

## 3. Posting decision table (binary terminal states)

For each pulled posting work-item, the connector reaches exactly one terminal outcome over
`connectorAckOutcome` (012 `OutcomeAckRequest`, outcome enum lines 552 / 676:
`posted | failed_transient | permanently_rejected`). Item-resolution failure is **absent** from
this table by design (rider R2 — it fails-to-DLQ in DP2 before offer).

| # | Condition at posting | Connector outcome | `reason.category` |
|---|---|---|---|
| 1 | All lines carry resolved `erpnextItemRef`; ERPNext accepts the submit | `posted` (+ `documentRef`) | — |
| 2 | Already posted (same `sourceSystem`+`externalId`); DP2 re-offers | `posted` — **echo the SAME `documentRef`** (idempotent, O-3) | — |
| 3 | Transient ERPNext failure (timeout, lock, temporary unavailability) | `failed_transient` (DP2 re-offers; no connector self-retry) | — |
| 4 | Closed accounting period at submit | `permanently_rejected` | `closed_period` |
| 5 | ERPNext validation failure (incl. unmapped UOM, malformed line) | `permanently_rejected` | `validation` |
| 6 | Unmapped ERPNext account at submit | `permanently_rejected` | `unmapped_account` |
| 7 | ERPNext rejects a disabled/non-sales Item at submit (should have DLQ'd upstream per R3) | `permanently_rejected` | `validation` (the Item *is* mapped — it carries an `erpnextItemRef` — so this is a submit-validation failure, not `unmapped_item`; use `other` if ERPNext signals a non-validation block) |
| 8 | Offered line missing `erpnextItemRef` (upstream contract violation; should be impossible per R2) | `permanently_rejected` + **STOP-and-raise** | `validation` |
| 9 | Other non-retryable ERPNext error | `permanently_rejected` | `other` |

**Invariant**: every work-item lands in exactly one terminal state —
`posted` XOR `failed_transient` XOR `permanently_rejected`. There is **no** silent partial, guess,
drop, or catch-all-Item path (Principle VI; spec SC-001). `permanently_rejected` always carries a
`reason.category` from the 012 **closed** set
(`validation | closed_period | unmapped_item | unmapped_account | other`, `RejectionReason` lines
651–653) — **no new wire reason is invented**; the connector maps its internal reasons onto this
existing taxonomy.

---

## 4. Idempotency & replay (Gate G5)

- **Replay key**: DP2 `sourceSystem` + `externalId` — the 012 wire idempotency anchor
  (`posting-feed.yaml` line 345: *"Provenance + dedup key (mirrors 008). The wire idempotency anchor
  (O-3)."*). The same logical sale maps to the same ERPNext document.
- **Ack replay**: `connectorAckOutcome` is `x-idempotency: required` (line 150). The same
  `Idempotency-Key` reused with the **same** logical outcome replays deterministically; reused with
  a **different** logical outcome returns `409 idempotency_key_conflict` (lines 168–169 / 277). The
  connector introduces **no** new idempotency primitive.
- **Duplicate `posted`**: echoes the existing ERPNext `documentRef` unchanged (O-2/O-3,
  lines 34 / 562–563). No second ERPNext document is created.
- The connector does **not** self-retry. A `failed_transient` returns control to DP2, which owns
  re-drive + DLQ + the 017 reconciliation flag.

---

## 5. UOM & money (retained from connector 004 US4)

- **UOM** — reconcile the DP2 free-text `unit` per the **signed** UOM decision
  (`docs/decisions/mapping-uom.md`, Option A: connector-side unit→ERPNext-UOM map). An **unmapped**
  unit fails closed as `permanently_rejected` / `validation` (row 5 above) — there is **no**
  `unmapped_uom` category in the 012 closed set; an unmapped unit is a line-validation failure,
  never a silent default (Principle VI).
- **Money** — represent every monetary value as an exact-decimal string + ISO-4217 currency code,
  per the 012 `DecimalAmount` (lines 293–) and `CurrencyCode` (lines 300–) shapes. Never a float.
- **Warehouse** (rider R5) — apply the DP2-pre-resolved store/warehouse identity generically
  (`{doctype, name}`); never guess. A missing DP-014 mapping fails-to-DLQ in DP2 before offer
  (`unmapped_store`-class) — the connector never sees an unmapped-warehouse offered work-item.

---

## 6. Payment Entry — gated sub-scope (rider R1)

The **signed target** is one submitted **Sales Invoice + its associated Payment Entry** per sale
(`posting-decision-rider-2026-06-05.md` §R1, citing `011-DR-POSTING §1`). The **first
implementation slice** is the **interim "submitted Sales Invoice / outstanding-AR only"** mode:

- **Not finance-complete.** Expected to produce unpaid/outstanding ERPNext Sales Invoices (open AR)
  until the tender/payment extension ships — an expected interim state, not a defect.
- Payment Entry is **gated** on ALL of: (1) a DP2 tender/payment fact model, (2) a 012 payment-
  carrying posting-feed extension (versioned, backward-compatible), (3) idempotent Payment-Entry
  creation in the connector, (4) payment repair/reconciliation semantics (017 extended).
- **Not ratified** (a STOP-and-raise if attempted): deriving a v1 Payment Entry from `posTotal`
  (fabricated tender DP2 does not own).

Payment-method mapping (connector side) is therefore **deferred** to this gated sub-scope and is
**not** part of the first interim slice.

---

## 7. Citation verification

| Claim | DP2 path | Verified |
|---|---|---|
| DP2-side resolution; connector applies, no lookup | `specs/011-…/decisions/posting-decision-rider-2026-06-05.md` §R2 | ✅ |
| No substitute item; disabled-Item fails-to-DLQ | same, §R3 | ✅ |
| Unknown-item ≠ unmapped; needs confirmed 013 mapping | same, §R4 | ✅ |
| Missing warehouse fails-to-DLQ; never guess | same, §R5 | ✅ |
| Payment Entry gated; interim AR-only; SI+PE target | same, §R1 | ✅ |
| `erpnextItemRef` required on every offered line | `packages/contracts/openapi/erpnext-connector/posting-feed.yaml` line 459 + 487–497 | ✅ |
| `ErpnextItemRef` = `{doctype:"Item", name}` (013 ref) | same, lines 604–627 | ✅ |
| `tenantProductRef` lineage-only, DP2-side resolution | same, lines 498–507 | ✅ |
| Outcome enum + closed `RejectionReason.category` set | same, lines 552 / 651–653 | ✅ |
| Idempotency anchor `sourceSystem`+`externalId` (O-3); ack `x-idempotency` | same, lines 345 / 150 / 168–169 | ✅ |
| Two-op surface `connectorPullPostings` / `connectorAckOutcome` | same, lines 107 / 149 | ✅ |
| 015 posting spec (planning, docs-only) + rider reference | `specs/015-pos-sale-posting-to-erpnext/spec.md` | ✅ |
