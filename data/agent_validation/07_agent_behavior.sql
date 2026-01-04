-- ============================================
-- AGENT BEHAVIOR ANALYSIS
-- Top 10 most active agents
-- ============================================

SELECT
    a.agent_id,
    a.age_group,
    a.income_bracket,
    ROUND(a.price_sensitivity, 2) as price_sensitivity,
    ROUND(a.coupon_affinity, 2) as coupon_affinity,
    COUNT(DISTINCT ss.id) as sessions_count,
    COUNT(DISTINCT o.id) as orders_count,
    COALESCE(ROUND(SUM(o.final_total), 2), 0) as total_spent
FROM agents a
LEFT JOIN users u ON a.user_id = u.id
LEFT JOIN shopping_sessions ss ON ss.user_id = u.id
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY a.agent_id, a.age_group, a.income_bracket, a.price_sensitivity, a.coupon_affinity
ORDER BY sessions_count DESC, orders_count DESC
LIMIT 10;
