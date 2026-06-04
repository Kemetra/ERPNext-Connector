# Feature Specification: Frappe App Foundation

**Feature Branch**: `001-frappe-app-foundation`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "001 Frappe App Foundation — Create the custom Frappe app foundation (retail_tower_erpnext_connector). Scope: Frappe app scaffold, app metadata, install policy, version pinning policy, Connector Settings DocType placeholder, local/staging setup notes. No ERP business mutation yet."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install the connector app on a staging ERPNext site (Priority: P1)

An integration operator installs the `retail_tower_erpnext_connector` app onto a staging
ERPNext site so the connector has a clean, isolated home alongside ERPNext without
altering ERPNext core behavior.

**Why this priority**: Nothing else in the connector roadmap can proceed until the app
installs cleanly. This is the minimum viable foundation — a successfully installed,
inspectable app is itself a deliverable that unblocks every later spec (002–008).

**Independent Test**: On a fresh staging ERPNext site, install the app and confirm it
appears in the site's installed-apps list, loads without error, and does not modify any
existing ERPNext records or behavior.

**Acceptance Scenarios**:

1. **Given** a fresh staging ERPNext site, **When** the operator installs the connector
   app, **Then** the app installs successfully and is listed among the site's installed
   apps.
2. **Given** the app is installed, **When** the operator loads the site, **Then** the site
   functions normally and no existing ERPNext product, stock, or sales data has changed.
3. **Given** the app is installed, **When** the operator inspects the app, **Then** the app
   metadata (name, description, publisher, license) is present and clearly identifies it as
   the Retail Tower ERPNext connector.

---

### User Story 2 - Locate the Connector Settings placeholder (Priority: P2)

After install, an operator opens the Connector Settings configuration surface to confirm a
single, discoverable place exists for future integration configuration — even though it
holds no live settings yet.

**Why this priority**: A known configuration anchor lets later specs (003 auth, 004 export)
attach settings without re-litigating where configuration lives. It delivers value as a
visible, navigable placeholder, but is not required for the app to install (US1).

**Independent Test**: With the app installed, the operator navigates to Connector Settings
and confirms it exists and opens, with no functional configuration fields required yet.

**Acceptance Scenarios**:

1. **Given** the app is installed, **When** the operator searches for Connector Settings,
   **Then** a single Connector Settings configuration record exists and can be opened.
2. **Given** Connector Settings is open, **When** the operator reviews it, **Then** it is
   clearly marked as a placeholder with no active integration behavior.

---

### User Story 3 - Follow the documented version & upgrade policy (Priority: P3)

A developer or operator preparing an install or upgrade reads the documented version
pinning and upgrade policy to know which ERPNext/Frappe versions are supported and how to
upgrade safely through staging.

**Why this priority**: Documentation prevents unsafe production upgrades (Constitution
Principle III) but is not required for the app to install or for Connector Settings to
exist. It hardens the foundation rather than enabling it.

**Independent Test**: A developer unfamiliar with the project can read the install and
version/upgrade documentation and correctly state the supported ERPNext/Frappe version
range and the required staging-before-production upgrade sequence.

**Acceptance Scenarios**:

1. **Given** the foundation documentation, **When** a developer reads it, **Then** the
   supported ERPNext and Frappe version range is explicit.
2. **Given** the upgrade policy, **When** an operator plans an upgrade, **Then** the
   documented sequence requires staging validation and a rehearsed backup/restore before
   any production change.

### Edge Cases

- What happens when the app is installed on an ERPNext site whose version falls outside the
  supported/pinned range? The documented policy MUST state this is unsupported and the
  expected operator action.
- What happens when the app is uninstalled? Uninstalling MUST leave ERPNext product, stock,
  and sales data unchanged (the app introduced no business mutations to reverse).
- What happens when install is attempted twice? A second install attempt MUST NOT corrupt
  the app state or duplicate the Connector Settings configuration record.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The connector MUST be packaged as a single custom Frappe app named
  `retail_tower_erpnext_connector`, installable onto an ERPNext site.
- **FR-002**: The app MUST carry clear metadata identifying its name, purpose
  (Retail Tower ↔ ERPNext connector), publisher, and license.
- **FR-003**: The app MUST install successfully on a staging ERPNext site within the
  supported version range without modifying ERPNext core behavior.
- **FR-004**: The app MUST provide a single Connector Settings configuration surface as a
  placeholder, discoverable after install, with no active integration behavior.
- **FR-005**: The app MUST NOT contain any DocType, hook, or scheduled action that creates,
  updates, or deletes product, stock, price, or sales data. *(Constitution Principle VII)*
- **FR-006**: The app MUST NOT fork ERPNext or embed copies of ERPNext/Frappe core code.
  *(Constitution Principle II)*
- **FR-007**: The supported ERPNext and Frappe version range MUST be explicitly pinned and
  documented as an install policy.
- **FR-008**: An upgrade and compatibility policy MUST be documented requiring upgrades to
  be validated in staging, with a rehearsed backup/restore, before any production change.
  *(Constitution Principle III)*
- **FR-009**: Local and staging setup steps MUST be documented sufficiently for a developer
  to install the app on a fresh staging ERPNext site without tribal knowledge.
- **FR-010**: Uninstalling the app MUST leave existing ERPNext business data unchanged.

### Key Entities *(include if feature involves data)*

- **Connector App**: The installable unit (`retail_tower_erpnext_connector`) and its
  identifying metadata; the container all future connector capabilities attach to.
- **Connector Settings**: A single configuration record acting as the future anchor for
  integration configuration; in this feature it exists only as an empty placeholder.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The app installs on a fresh staging ERPNext site on the first attempt with
  zero install errors.
- **SC-002**: After install, an operator can locate and open Connector Settings in under
  1 minute of navigation, using only the setup docs.
- **SC-003**: 100% of ERPNext product, stock, and sales records are unchanged before and
  after install and uninstall (no business mutation introduced).
- **SC-004**: A developer unfamiliar with the project can complete a staging install using
  only the documentation, with no undocumented steps required.
- **SC-005**: The supported ERPNext/Frappe version range and the staging-before-production
  upgrade sequence are documented and unambiguous to a first-time reader.

## Assumptions

- The target ERP backend is a standard ERPNext deployment; ERPNext, Frappe, and the
  DocType model are fixed domain constraints of this project (per README and constitution),
  not choices made within this feature.
- The supported version range is pinned to the current stable ERPNext/Frappe major line
  (ERPNext v15 / Frappe v15) for the foundation; the exact pin is recorded in the install
  policy and revised through the documented upgrade process.
- Version compatibility is *declared and documented*, not enforced at install time; the
  foundation introduces no install-blocking version validation logic (consistent with the
  no-logic scaffold scope and the Edge Cases policy stance).
- A staging ERPNext site is available for install validation; production install is out of
  scope for this feature.
- This feature scaffolds the foundation only. Catalog, inventory, sales posting, tax, and
  Data-Pulse-2 authentication are explicitly out of scope and are delivered by later specs
  (002–008) after their contracts are reviewed.
