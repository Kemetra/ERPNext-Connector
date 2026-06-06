-- Tier-2 live-flow e2e — DP2 seed for ONE pending sale_post work-item + a connector token.
-- Direct-seeds a `pending` erpnext_posting_status row (vs driving the real
-- sale.captured -> worker -> resolveEligibility pipeline). Proves the CONNECTOR loop;
-- does NOT exercise DP2 resolveEligibility (see tier2-e2e-milestone memory).
--
-- Idempotent: clears prior e2e rows by the fixed UUIDs first. Runs under one tenant GUC so
-- FORCE-RLS inserts pass. Run:
--   docker exec -i dp2-postgres-dev psql -U dp2 -d data_pulse_2 -v ON_ERROR_STOP=1 < dp2-seed.sql
--
-- The RAW connector token is printed at the end — present it as `Authorization: Bearer <raw>`.

\set ON_ERROR_STOP on
\set tenant   '11111111-1111-1111-1111-111111111111'
\set store    '22222222-2222-2222-2222-222222222222'
\set usr      '33333333-3333-3333-3333-333333333333'
\set product  '66666666-6666-6666-6666-666666666666'
\set token    '88888888-8888-8888-8888-888888888888'
-- NOTE: the sale, sale_line and posting-status rows use FRESH gen_random_uuid() ids + a UNIQUE
-- external_id every run (see the DO block below) — NOT fixed ids. Reusing a fixed posting id makes
-- the connector resend the SAME ack idempotency key ({workItemRef}:permanently_rejected) against
-- DP2's sticky ack-idempotency store, which 409s on a re-run (Codex #21 finding). A fresh id per run
-- keeps this seed genuinely rerunnable.
-- The raw bearer the connector presents; server stores only sha256(raw). 43-char base64url-ish.
\set rawtoken 'rt_e2e_connector_token_0123456789abcdefghijABCD'

BEGIN;
-- Platform-admin context so the seed can write across tenant-scoped FORCE-RLS tables.
SET LOCAL app.is_platform_admin = 'true';
SET LOCAL app.current_tenant = :'tenant';

-- Clean prior e2e rows (child -> parent order). The sale/posting rows are cleaned by their stable
-- E2E marker (external_id / source_system) rather than a fixed id, because each run mints fresh ids.
DELETE FROM erpnext_posting_status
  WHERE tenant_id = :'tenant' AND source_system = 'retail_tower_pos' AND external_id LIKE 'E2E-SALE-%';
DELETE FROM auth_tokens            WHERE id = :'token';
DELETE FROM erpnext_item_map       WHERE tenant_product_id = :'product';
DELETE FROM erpnext_warehouse_map  WHERE store_id = :'store';
DELETE FROM sale_lines
  WHERE sale_id IN (SELECT id FROM sales WHERE tenant_id = :'tenant' AND external_id LIKE 'E2E-SALE-%');
DELETE FROM sales                  WHERE tenant_id = :'tenant' AND external_id LIKE 'E2E-SALE-%';
DELETE FROM tenant_products        WHERE id = :'product';
DELETE FROM users                  WHERE id = :'usr';
DELETE FROM stores                 WHERE id = :'store';
DELETE FROM tenants                WHERE id = :'tenant';

-- 1) tenant -> store + user
INSERT INTO tenants (id, slug, name, status, default_currency_code)
  VALUES (:'tenant', 'rt-e2e', 'RT E2E Tenant', 'active', 'USD');
INSERT INTO stores (id, tenant_id, code, name, is_active, timezone)
  VALUES (:'store', :'tenant', 'E2E', 'E2E Store', true, 'UTC');
-- users is GLOBAL (no tenant_id; tenant linkage is via the memberships table). For this
-- direct-seed e2e the user is only an FK anchor for sales.created_by + auth_tokens.user_id.
INSERT INTO users (id, email, is_platform_admin)
  VALUES (:'usr', 'e2e-connector@rt.test', false);

-- 1b) tenant product — the catalog entity sale_lines.tenant_product_ref + the item-map point at.
INSERT INTO tenant_products (id, tenant_id, name, tax_category, is_active, created_by, updated_by)
  VALUES (:'product', :'tenant', 'E2E Test Product', 'standard', true, :'usr', :'usr');

-- 2) sale + one line + the pending posting row — all with FRESH ids and a UNIQUE external_id per
-- run (so the connector's ack idempotency key is never reused; Codex #21). One CTE chain threads
-- the generated sale id through the line and the posting-status row. external_id is unique via a
-- clock-stamp suffix; sequence on the posting row is GENERATED ALWAYS (omitted).
WITH new_ids AS (
  SELECT gen_random_uuid() AS sale_id,
         'E2E-SALE-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS') AS ext_id
), s AS (
  INSERT INTO sales (id, tenant_id, store_id, currency_code, pos_total, occurred_at,
                     business_date, source_system, external_id, payload_hash, created_by)
  SELECT sale_id, :'tenant', :'store', 'USD', 19.99, now(),
         CURRENT_DATE, 'retail_tower_pos', ext_id, repeat('a',64), :'usr'
    FROM new_ids
  RETURNING id, external_id
), l AS (
  INSERT INTO sale_lines (id, sale_id, tenant_id, store_id, line_name, unit_price,
                          currency_code, quantity, line_amount, tax_amount, unit, tenant_product_ref)
  SELECT gen_random_uuid(), s.id, :'tenant', :'store', 'Line 1', 19.99,
         'USD', 1, 19.99, NULL, 'each', :'product'
    FROM s
)
-- 5) PENDING posting-status row — the feed serves this (sequence GENERATED ALWAYS, omitted).
INSERT INTO erpnext_posting_status (id, tenant_id, store_id, sale_id, kind, source_ref_id,
                                    source_system, external_id, payload_hash, status)
SELECT gen_random_uuid(), :'tenant', :'store', s.id, 'sale_post', s.id,
       'retail_tower_pos', s.external_id, repeat('a',64), 'pending'
  FROM s;

-- 3) CONFIRMED item map: tenant_product_ref -> ERPNext Item code.
INSERT INTO erpnext_item_map (id, tenant_id, tenant_product_id, erpnext_item_ref, state,
                              suggestion_source, confirmed_by, confirmed_at)
  VALUES (gen_random_uuid(), :'tenant', :'product', 'TEST-ITEM-01', 'confirmed',
          'manual', :'usr', now());

-- 4) ACTIVE warehouse map: store -> ERPNext Warehouse name.
INSERT INTO erpnext_warehouse_map (id, tenant_id, store_id, purpose, erpnext_warehouse_ref, set_by)
  VALUES (gen_random_uuid(), :'tenant', :'store', 'stock', 'Stores - E2E', :'usr');

-- 6) Connector bearer token: store sha256(raw) bytes; scope=connector; user-anchored (CHECK
--    requires exactly one of user_id/device_id for non-pos_operator); 1-day expiry.
INSERT INTO auth_tokens (id, token_hash, tenant_id, user_id, scope, expires_at)
  VALUES (:'token', sha256(convert_to(:'rawtoken','UTF8')), :'tenant', :'usr',
          'connector', now() + interval '1 day');

COMMIT;

\echo '=== RAW connector bearer token (Authorization: Bearer <this>):'
SELECT :'rawtoken' AS raw_token;
\echo '=== SEED OK — the freshly-minted pending row the feed will serve (fresh id + external_id):'
SELECT id AS work_item_ref, status, sale_id, external_id, sequence
  FROM erpnext_posting_status
 WHERE tenant_id = :'tenant' AND source_system = 'retail_tower_pos' AND status = 'pending'
 ORDER BY sequence DESC LIMIT 1;
