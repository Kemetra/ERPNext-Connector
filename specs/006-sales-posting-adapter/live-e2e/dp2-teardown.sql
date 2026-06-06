-- Tier-2 live-e2e teardown — remove all seeded rows + the connector token from dp2-postgres-dev.
-- Mirrors dp2-seed.sql's DELETE block (child -> parent order). Idempotent.
BEGIN;
SET LOCAL app.is_platform_admin = 'true';
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
DELETE FROM erpnext_posting_status WHERE id = '77777777-7777-7777-7777-777777777777';
DELETE FROM auth_tokens            WHERE id = '88888888-8888-8888-8888-888888888888';
DELETE FROM erpnext_item_map       WHERE tenant_product_id = '66666666-6666-6666-6666-666666666666';
DELETE FROM erpnext_warehouse_map  WHERE store_id = '22222222-2222-2222-2222-222222222222';
DELETE FROM sale_lines             WHERE id = '55555555-5555-5555-5555-555555555555';
DELETE FROM sales                  WHERE id = '44444444-4444-4444-4444-444444444444';
DELETE FROM tenant_products        WHERE id = '66666666-6666-6666-6666-666666666666';
DELETE FROM users                  WHERE id = '33333333-3333-3333-3333-333333333333';
DELETE FROM stores                 WHERE id = '22222222-2222-2222-2222-222222222222';
DELETE FROM tenants                WHERE id = '11111111-1111-1111-1111-111111111111';
COMMIT;
\echo '=== teardown verification (all should be 0) ==='
SELECT 'connector_tokens' AS k, count(*) AS n FROM auth_tokens WHERE scope='connector'
UNION ALL SELECT 'e2e_sales', count(*) FROM sales WHERE external_id='E2E-SALE-0001'
UNION ALL SELECT 'e2e_tenants', count(*) FROM tenants WHERE id='11111111-1111-1111-1111-111111111111'
UNION ALL SELECT 'e2e_postings', count(*) FROM erpnext_posting_status WHERE id='77777777-7777-7777-7777-777777777777';
