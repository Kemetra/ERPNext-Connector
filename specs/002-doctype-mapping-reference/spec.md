# Feature Specification: DocType Mapping Reference

**Feature Branch**: `002-doctype-mapping-reference`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "002 DocType Mapping Reference — document how ERPNext concepts map to Retail Tower concepts consumed via Data-Pulse-2. Backend reference repo: Data-Pulse-2."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the canonical mapping matrix (Priority: P1)

A connector developer or integration reviewer opens the mapping reference to see, in one
place, how each ERPNext concept corresponds to a Retail Tower concept (as modeled in
Data-Pulse-2), who owns the truth for it, and whether the mapping is resolved, needs a
signed decision, or is deferred to a later spec.

**Why this priority**: Every later connector spec (003 auth, 004 product export, 005
inventory, 006 sales posting, 007 tax) depends on an agreed vocabulary. Without a single
reviewed mapping, each spec re-litigates "what does an ERPNext Item correspond to?" — the
matrix is the foundation that unblocks them. It delivers value on its own as a reviewable
reference.

**Independent Test**: A reviewer reads the matrix and can correctly state, for each of the
mapping areas (Company, Warehouse, Item, Barcode, UOM, Price List, Sale/Invoice, Payment,
Return), the Retail Tower / Data-Pulse-2 counterpart, the owner of truth, and the mapping
status — without consulting any other document.

**Acceptance Scenarios**:

1. **Given** the mapping reference, **When** a reviewer looks up an ERPNext concept (e.g.
   "Item"), **Then** the matrix shows its Retail Tower counterpart, the owner of truth, the
   status, and a citation to the authoritative Data-Pulse-2 source.
2. **Given** the mapping reference, **When** a reviewer scans for unresolved items, **Then**
   every mapping marked "Decision needed" is listed with the specific open question.
3. **Given** the mapping reference, **When** a reviewer checks a deferred concept (e.g.
   Payment), **Then** the matrix names the later spec that will own it.

---

### User Story 2 - Trust Data-Pulse-2 as the source of the Retail Tower side (Priority: P2)

A reviewer needs assurance that the Retail Tower side of every mapping is taken from
Data-Pulse-2's authoritative model (its data contracts and the connector posting contract),
not re-invented in the connector repository — so the connector and the backend cannot drift
apart.

**Why this priority**: Data-Pulse-2 is the only orchestration boundary (constitution
Principle I). A connector-owned mapping that restates DP2's model would create a second
source of truth that silently drifts. This story makes the reference a *citation* of DP2's
model rather than a parallel definition. Important, but secondary to having the matrix (US1).

**Independent Test**: For each Retail Tower concept in the matrix, the cited Data-Pulse-2
source can be located and confirms the named counterpart; no Retail Tower concept is defined
only in the connector repo.

**Acceptance Scenarios**:

1. **Given** any matrix row, **When** a reviewer follows the cited Data-Pulse-2 source,
   **Then** that source confirms the Retail Tower counterpart named in the row.
2. **Given** the reference, **When** a reviewer checks how ERPNext documents are addressed,
   **Then** the reference uses only the generic Retail Tower–facing addressing exposed by
   Data-Pulse-2 (a doctype + name reference), not ERPNext field-level names.

---

### User Story 3 - Sign off ambiguous mappings as decisions (Priority: P3)

A reviewer with decision authority records a signed decision for each ambiguous mapping, so
that downstream implementation specs may not begin on that concept until its decision is
agreed.

**Why this priority**: The README's exit criterion for 002 is that ambiguous mappings are
recorded as decisions and no implementation starts before required decisions are signed.
This story captures the governance outcome. It depends on the matrix existing (US1) and is
the gate that protects later specs.

**Independent Test**: Each "Decision needed" mapping has an associated decision record with
options and a sign-off line; a reviewer can tell which decisions are signed and which remain
open.

**Acceptance Scenarios**:

1. **Given** an ambiguous mapping, **When** a reviewer opens its decision record, **Then**
   the record states the question, the options considered, and a place for sign-off.
2. **Given** the set of decisions, **When** a planner checks whether a later spec may start,
   **Then** unsigned decisions for that concept are clearly flagged as blocking.

### Edge Cases

- What happens when an ERPNext concept has **no** Retail Tower counterpart in Data-Pulse-2
  (e.g. UOM has no master entity; Price List is not modeled as an entity)? The matrix MUST
  represent this explicitly (status "Decision needed" or "Resolved — reference only"), not
  omit the row.
- What happens when Data-Pulse-2's model and an older repository document disagree (e.g. a
  stale roadmap)? The reference MUST prefer Data-Pulse-2's current model/contracts and note
  the superseded source.
- What happens when a concept is owned by ERPNext, not Retail Tower (e.g. accounting/GL,
  Item identity)? The "owner of truth" column MUST record this so the connector does not
  treat it as Retail Tower–authoritative.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The reference MUST provide a single mapping matrix covering at least these
  ERPNext concepts: Company, Warehouse, Item, Item Barcode, UOM, Price List, POS Invoice /
  Sales Invoice, Payment Entry, and Return/Refund.
- **FR-002**: Each matrix row MUST record: the ERPNext concept, its Retail Tower counterpart
  (as modeled in Data-Pulse-2), the **owner of truth**, a **status** (Resolved /
  Decision needed / Deferred to spec NNN), and a **citation to the authoritative
  Data-Pulse-2 source**.
- **FR-003**: The Retail Tower side of every mapping MUST be sourced from Data-Pulse-2's
  authoritative model (its data contracts and the connector posting contract), not defined
  independently in the connector repository. *(Constitution Principle I)*
- **FR-004**: The reference MUST address ERPNext documents only via the generic Retail
  Tower–facing reference exposed by Data-Pulse-2 (a doctype + name pair), and MUST NOT
  depend on ERPNext field-level names, to preserve version independence. *(Constitution
  Principle II)*
- **FR-005**: Every mapping with status "Decision needed" MUST have an associated decision
  record stating the open question, the options considered, and a sign-off line.
- **FR-006**: The reference MUST state, for each deferred concept, the later spec that will
  own it (e.g. Payment Entry → sales posting / tender; tax → spec 007).
- **FR-007**: Where Data-Pulse-2 and an older repository document disagree, the reference
  MUST cite Data-Pulse-2's current model as authoritative and note the superseded source.
- **FR-008**: The reference MUST NOT implement any product, stock, price, sales, or payment
  mapping behavior; it is a documentation and decision artifact only. *(Constitution
  Principle VII)*
- **FR-009**: The reference MUST record the **identity correlation** used to link a Retail
  Tower product to an ERPNext Item (the confirmed product-to-Item mapping concept), at the
  concept level, citing the Data-Pulse-2 source.
- **FR-010**: The reference MUST keep mappings at **concept level**; field-by-field document
  construction is explicitly out of scope and owned by later implementation specs.

### Key Entities *(include if feature involves data)*

- **Mapping Matrix**: The reviewed table relating each ERPNext concept to its Retail Tower /
  Data-Pulse-2 counterpart, with owner of truth, status, and source citation.
- **Mapping Decision Record**: A per-ambiguity record (question, options, sign-off) that
  gates downstream implementation on the corresponding concept.
- **Product-to-Item Correlation**: The concept-level description of how a confirmed Retail
  Tower product links to an ERPNext Item reference (owned by Data-Pulse-2's model).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the listed mapping areas (Company, Warehouse, Item, Barcode, UOM,
  Price List, Sale/Invoice, Payment, Return) appear as rows in the matrix with a status.
- **SC-002**: A reviewer unfamiliar with the project can, using only the reference, correctly
  state the Retail Tower counterpart and owner of truth for any listed ERPNext concept.
- **SC-003**: 100% of "Decision needed" mappings have an associated decision record with an
  explicit sign-off line.
- **SC-004**: Every matrix row cites a locatable Data-Pulse-2 source, and each citation
  confirms the named counterpart (no Retail Tower concept defined only in this repo).
- **SC-005**: A planner can determine, for any later spec (003–007), whether its prerequisite
  mapping decisions are signed or still blocking, from the reference alone.

## Assumptions

- **Data-Pulse-2 is the authoritative source** for the Retail Tower side of every mapping.
  Its data contracts and the connector posting contract (which already drafts the
  ERPNext↔Retail Tower concept mapping and the product-to-Item correlation) are treated as
  truth; this reference cites them rather than redefining them.
- **Within Data-Pulse-2, code and contracts outrank prose.** Where the Data-Pulse-2 schema
  and connector contract (its migrations and the connector posting contract) diverge from
  Data-Pulse-2 prose documents, the schema/contract is authoritative and the prose is noted
  as superseded — consistent with FR-007 and the observed drift of older roadmap prose.
- **This feature is a documentation + decision artifact only** — a mapping matrix and
  decision records. No connector code, DocType, or mapping logic is produced (that is spec
  006 and later). Stated to satisfy constitution Principle VII.
- **Concept altitude**: the reference maps concepts, not ERPNext field names or document
  construction. Field-level mapping and document building belong to the implementation specs.
- **Known structural realities from Data-Pulse-2** are carried into the matrix as statuses,
  not treated as open questions to the user:
  - UOM has no master entity in Data-Pulse-2 (unit is a free-text value) → **Decision needed**.
  - Price List is not a Data-Pulse-2 entity; amounts are authoritative there, ERPNext Price
    List is a reference only → **Resolved (reference only)**.
  - Payment Entry / tender is not modeled in Data-Pulse-2 yet → **Deferred** to the sales
    posting / tender work.
  - Customer is not modeled in Data-Pulse-2 (walk-in retail) → recorded as ERPNext-owned /
    Deferred.
- The owning specs for deferred concepts follow the README roadmap (003 auth, 004 product,
  005 inventory, 006 sales posting, 007 tax/fiscal).
