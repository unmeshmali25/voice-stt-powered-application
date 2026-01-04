-- ============================================
-- CHECK SCHEMA - Verify which tables have is_simulated/is_simulation flags
-- ============================================

-- Check shopping_sessions columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'shopping_sessions'
  AND column_name LIKE '%simul%'
ORDER BY column_name;

-- Check orders columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'orders'
  AND column_name LIKE '%simul%'
ORDER BY column_name;

-- Check if any sessions exist without is_simulated flag
SELECT
    'Total shopping_sessions' as metric,
    COUNT(*) as count
FROM shopping_sessions;

-- Check if any orders exist
SELECT
    'Total orders' as metric,
    COUNT(*) as count
FROM orders;
