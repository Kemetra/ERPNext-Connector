# Decision: DP2 Connector Token Scope

**Spec**: 003 — Data-Pulse Auth & API Policy | **Status**: OPEN | **Date raised**: 2026-06-04
**Blocks**: SC-001 (staging authentication)

## Question

The connector must authenticate to Data-Pulse-2 as a tenant-scoped machine principal
presenting an opaque bearer token (`connectorBearer`, per `posting-feed.yaml`).

**Which DP2 token scope should authenticate the connector machine principal — and does one
exist today?**

## Context (cited)

`packages/db/src/schema/auth_tokens.ts` (line 61) defines the **authoritative, exhaustive**
bearer-scope type:

```typescript
type BearerAuthScope = "dashboard_api" | "pos" | "pos_operator";
// AuthTokenScope (line 64) = BearerAuthScope | SingleUseTokenScope
```

`packages/auth/src/types.ts` (line 58) carries a **narrower mirror** used by the auth package,
omitting `pos_operator`:

```typescript
export type AuthTokenScope = "dashboard_api" | "pos";   // staler/narrower copy
```

`apps/api/src/auth/auth.guard.ts` defines the set of scopes accepted for general bearer
API authentication:

```typescript
export const BEARER_AUTH_SCOPES = new Set<BearerAuthScope>([
  "dashboard_api",
  "pos",
  "pos_operator",
]);
```

(Single-use workflow scopes — `password_reset`, `email_verify` — are explicitly excluded
from `BEARER_AUTH_SCOPES`; they are never valid API credentials.)

None of the bearer scopes present in DP2 today — `dashboard_api`, `pos`, `pos_operator` — is a
dedicated connector/machine-principal scope. The fact that `pos_operator` already exists in the
db-schema `BearerAuthScope` (line 61) but is **absent** from the narrower
`packages/auth/src/types.ts` copy (line 58) shows DP2 scope definitions are actively evolving;
adding a new scope is a precedented change. Provisioning a dedicated connector scope is a
Data-Pulse-2-side change that this connector cannot make unilaterally.

The spec records this explicitly (spec.md Dependencies): "Data-Pulse-2's current token
scopes are operational (`dashboard_api`, `pos`); a dedicated connector/machine-principal
scope does not yet exist in DP2."

## Options

| # | Option | Implication |
|---|--------|-------------|
| A | **DP2 provisions a new dedicated scope (e.g. `connector` or `erpnext_connector`) for the machine principal.** The connector is issued a token under this scope; the pull/ack endpoints require it. | Correct least-privilege model: the machine principal is distinct from dashboard humans and POS devices. The scope name is unambiguous in audit logs. Requires a DP2-side change (schema migration for `AuthTokenScope`, guard update, endpoint guard). This is the precedented path — `pos_operator` shows the pattern. Blocks staging auth until DP2 ships it. |
| B | Reuse the `dashboard_api` scope for the connector token. | Immediate unblock with zero DP2 changes. Violates least privilege: conflates a machine principal (no user, no session, no store binding) with dashboard human tokens. Any `dashboard_api` guard grants the connector access to dashboard-human-scoped endpoints — an overbroad surface. Complicates revocation and audit. Not recommended. |
| C | Reuse the `pos` or `pos_operator` scope for the connector token. | `pos_operator` is bound to `(user, device, tenant_id, store_id)` per `auth.guard.ts` lines 73-75; the connector is a tenant-level machine principal with no user, device, or store binding. Plain `pos` carries **no** store binding — it passes through as `null` (`auth.guard.ts` lines 76-77, `tenant-context.guard.ts` `resolveToken` lines 163-167) — but it is a POS-device/session scope, semantically wrong for a tenant-level machine principal. Reusing either conflates a cross-store machine principal with a point-of-sale identity and produces misleading audit records. Not recommended. |

## Recommendation

**Option A** — DP2 provisions a new dedicated connector scope (e.g. `connector` or
`erpnext_connector`). It is the only option consistent with the least-privilege principle
and the connector's machine-principal identity (tenant-scoped, revocable, no user/device
binding). The `pos_operator` precedent confirms that adding a new bearer scope is a routine
DP2-side operation (a new union member in `BearerAuthScope` in
`packages/db/src/schema/auth_tokens.ts`, the mirror in `packages/auth/src/types.ts`, plus a
`BEARER_AUTH_SCOPES` guard allowlist entry). This connector should request that scope from the
DP2 team; it MUST NOT reuse an existing scope as a workaround.

Until DP2 provisions this scope and issues the connector its token, staging authentication
(SC-001) is blocked. This decision record is the artefact that tracks the dependency.

## Sign-off

- [ ] **Decision signed** — by: ________________  date: __________
- Until signed, SC-001 (staging authentication) MUST NOT be treated as unblocked, and
  connector token provisioning MUST NOT proceed with a substitute scope.
