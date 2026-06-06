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
\set sale     '44444444-4444-4444-4444-444444444444'
\set line     '55555555-5555-5555-5555-555555555555'
\set product  '66666666-6666-6666-6666-666666666666'
\set posting  '77777777-7777-7777-7777-777777777777'
\set token    '88888888-8888-8888-8888-888888888888'
-- The raw bearer the connector presents; server stores only sha256(raw). 43-char base64url-ish.
\set rawtoken 'rt_e2e_connector_token_0123456789abcdefghijABCD'

BEGIN;
-- Platform-admin context so the seed can write across tenant-scoped FORCE-RLS tables.
SET LOCAL app.is_platform_admin = 'true';
SET LOCAL app.current_tenant = :'tenant';

-- Clean prior e2e rows (child -> parent order).
DELETE FROM erpnext_posting_status WHERE id = :'posting';
DELETE FROM auth_tokens            WHERE id = :'token';
DELETE FROM erpnext_item_map       WHERE tenant_product_id = :'product';
DELETE FROM erpnext_warehouse_map  WHERE store_id = :'store';
DELETE FROM sale_lines             WHERE id = :'line';
DELETE FROM sales                  WHERE id = :'sale';
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

-- 2) sale + one line (tenant_product_ref = the mapped product)
INSERT INTO sales (id, tenant_id, store_id, currency_code, pos_total, occurred_at,
                   business_date, source_system, external_id, payload_hash, created_by)
  VALUES (:'sale', :'tenant', :'store', 'USD', 19.99, now(),
          CURRENT_DATE, 'retail_tower_pos', 'E2E-SALE-0001',
          repeat('a',64), :'usr');
INSERT INTO sale_lines (id, sale_id, tenant_id, store_id, line_name, unit_price,
                        currency_code, quantity, line_amount, tax_amount, unit, tenant_product_ref)
  VALUES (:'line', :'sale', :'tenant', :'store', 'Line 1', 19.99,
          'USD', 1, 19.99, NULL, 'each', :'product');

-- 3) CONFIRMED item map: tenant_product_ref -> ERPNext Item code.
INSERT INTO erpnext_item_map (id, tenant_id, tenant_product_id, erpnext_item_ref, state,
                              suggestion_source, confirmed_by, confirmed_at)
  VALUES (gen_random_uuid(), :'tenant', :'product', 'TEST-ITEM-01', 'confirmed',
          'manual', :'usr', now());

-- 4) ACTIVE warehouse map: store -> ERPNext Warehouse name.
INSERT INTO erpnext_warehouse_map (id, tenant_id, store_id, purpose, erpnext_warehouse_ref, set_by)
  VALUES (gen_random_uuid(), :'tenant', :'store', 'stock', 'Stores - E2E', :'usr');

-- 5) PENDING posting-status row — the feed serves this. `sequence` is GENERATED ALWAYS: omit it.
INSERT INTO erpnext_posting_status (id, tenant_id, store_id, sale_id, kind, source_ref_id,
                                    source_system, external_id, payload_hash, status)
  VALUES (:'posting', :'tenant', :'store', :'sale', 'sale_post', :'sale',
          'retail_tower_pos', 'E2E-SALE-0001', repeat('a',64), 'pending');

-- 6) Connector bearer token: store sha256(raw) bytes; scope=connector; user-anchored (CHECK
--    requires exactly one of user_id/device_id for non-pos_operator); 1-day expiry.
INSERT INTO auth_tokens (id, token_hash, tenant_id, user_id, scope, expires_at)
  VALUES (:'token', sha256(convert_to(:'rawtoken','UTF8')), :'tenant', :'usr',
          'connector', now() + interval '1 day');

COMMIT;

\echo '=== SEED OK. workItemRef (posting id):'
SELECT :'posting' AS work_item_ref;
\echo '=== RAW connector bearer token (Authorization: Bearer <this>):'
SELECT :'rawtoken' AS raw_token;
\echo '=== verify feed-visible pending row:'
SELECT id, status, sale_id, sequence FROM erpnext_posting_status WHERE id = :'posting';
