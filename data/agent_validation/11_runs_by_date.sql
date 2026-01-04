-- ============================================
-- SIMULATION RUNS BY DATE
-- Group data by time periods to identify separate runs
-- ============================================

-- Sessions grouped by hour
SELECT
    DATE_TRUNC('hour', started_at) as run_hour,
    COUNT(DISTINCT user_id) as unique_agents,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as checkouts,
    COUNT(CASE WHEN status = 'abandoned' THEN 1 END) as abandoned,
    MIN(started_at) as first_session,
    MAX(ended_at) as last_session
FROM shopping_sessions
GROUP BY DATE_TRUNC('hour', started_at)
ORDER BY run_hour DESC
LIMIT 20;
