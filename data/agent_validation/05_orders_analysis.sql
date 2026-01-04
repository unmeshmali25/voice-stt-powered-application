-- ============================================
-- ORDERS ANALYSIS
-- Detailed order statistics and relationships
-- ============================================

-- Orders analysis (all data)
\echo 'Running orders analysis (all data)...'

SELECT
    COUNT(DISTINCT o.id) as total_orders,
    COUNT(DISTINCT o.shopping_session_id) as sessions_with_orders,
    ROUND(AVG(o.final_total), 2) as avg_order_value,
    ROUND(MIN(o.final_total), 2) as min_order_value,
    ROUND(MAX(o.final_total), 2) as max_order_value,
    ROUND(SUM(o.final_total), 2) as total_revenue,
    ROUND(SUM(o.discount_total), 2) as total_discounts
FROM orders o
WHERE o.shopping_session_id IS NOT NULL;

-- Orders analysis (simulated data only)
\echo 'Running orders analysis (simulated data only, is_simulated=true)...'

SELECT
    COUNT(DISTINCT o.id) as total_orders,
    COUNT(DISTINCT o.shopping_session_id) as sessions_with_orders,
    ROUND(AVG(o.final_total), 2) as avg_order_value,
    ROUND(MIN(o.final_total), 2) as min_order_value,
    ROUND(MAX(o.final_total), 2) as max_order_value,
    ROUND(SUM(o.final_total), 2) as total_revenue,
    ROUND(SUM(o.discount_total), 2) as total_discounts
FROM orders o
JOIN shopping_sessions s ON o.shopping_session_id = s.id
WHERE o.shopping_session_id IS NOT NULL
  AND s.is_simulated = true;
