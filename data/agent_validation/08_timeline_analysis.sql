-- ============================================
-- TIMELINE ANALYSIS
-- Session activity over time (hourly breakdown)
-- ============================================

SELECT
    DATE_TRUNC('hour', started_at) as hour,
    COUNT(*) as sessions_started,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN status = 'abandoned' THEN 1 END) as abandoned,
    ROUND(
        COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / COUNT(*),
        2
    ) as completion_rate_pct
FROM shopping_sessions
GROUP BY DATE_TRUNC('hour', started_at)
ORDER BY hour;
