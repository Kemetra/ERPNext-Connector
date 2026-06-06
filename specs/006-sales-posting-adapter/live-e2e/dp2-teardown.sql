-- Tier-2 live-e2e teardown — remove all seeded rows + the connector token from dp2-postgres-dev.
-- Mirrors dp2-seed.sql's DELETE block (child -> parent order). Idempotent.
-- The sale/posting rows now use fresh ids + the 'E2E-SALE-%' external_id marker (see dp2-seed.sql),
-- so clean them by marker, not by fixed id. tenant/store/user/product/token stay fixed-id.
BEGIN;
SET LOCAL app.is_platform_admin = 'true';
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
DELETE FROM erpnext_posting_status
  WHERE tenant_id = '11111111-1111-1111-1111-111111111111' AND external_id LIKE 'E2E-SALE-%';
DELETE FROM auth_tokens            WHERE id = '88888888-8888-8888-8888-888888888888';
DELETE FROM erpnext_item_map       WHERE tenant_product_id = '66666666-6666-6666-6666-666666666666';
DELETE FROM erpnext_warehouse_map  WHERE store_id = '22222222-2222-2222-2222-222222222222';
DELETE FROM sale_lines
  WHERE sale_id IN (SELECT id FROM sales
                     WHERE tenant_id = '11111111-1111-1111-1111-111111111111' AND external_id LIKE 'E2E-SALE-%');
DELETE FROM sales
  WHERE tenant_id = '11111111-1111-1111-1111-111111111111' AND external_id LIKE 'E2E-SALE-%';
DELETE FROM tenant_products        WHERE id = '66666666-6666-6666-6666-666666666666';
DELETE FROM users                  WHERE id = '33333333-3333-3333-3333-333333333333';
DELETE FROM stores                 WHERE id = '22222222-2222-2222-2222-222222222222';
DELETE FROM tenants                WHERE id = '11111111-1111-1111-1111-111111111111';
COMMIT;
\echo '=== teardown verification (all should be 0) ==='
SELECT 'connector_tokens' AS k, count(*) AS n FROM auth_tokens WHERE scope='connector'
UNION ALL SELECT 'e2e_sales', count(*) FROM sales WHERE external_id LIKE 'E2E-SALE-%'
UNION ALL SELECT 'e2e_tenants', count(*) FROM tenants WHERE id='11111111-1111-1111-1111-111111111111'
UNION ALL SELECT 'e2e_postings', count(*) FROM erpnext_posting_status WHERE external_id LIKE 'E2E-SALE-%';
