-- ============================================
-- DIAGNOSTIC QUERIES
-- Investigate why values don't match expected
-- ============================================

-- Check how many simulation runs exist
SELECT
    'Total simulation runs' as metric,
    COUNT(DISTINCT cycle_number) as count
FROM offer_cycles
WHERE is_simulation = true;

-- Check date range of sessions
SELECT
    'Session Date Range' as metric,
    MIN(started_at) as earliest_session,
    MAX(started_at) as latest_session,
    MAX(started_at) - MIN(started_at) as time_span
FROM shopping_sessions;

-- Check if there are multiple sessions per agent
SELECT
    'Sessions per Agent' as metric,
    ROUND(AVG(session_count), 2) as avg_sessions_per_agent,
    MAX(session_count) as max_sessions_per_agent
FROM (
    SELECT
        user_id,
        COUNT(*) as session_count
    FROM shopping_sessions
    GROUP BY user_id
) subquery;

-- Check agent creation dates
SELECT
    'Agent Creation Range' as metric,
    MIN(created_at) as first_agent,
    MAX(created_at) as last_agent,
    MAX(created_at) - MIN(created_at) as time_span
FROM agents;

-- Check offer cycles
SELECT
    cycle_number,
    started_at,
    ends_at,
    is_simulation,
    (SELECT COUNT(*) FROM user_coupons WHERE offer_cycle_id = offer_cycles.id) as coupons_in_cycle
FROM offer_cycles
WHERE is_simulation = true
ORDER BY cycle_number;

-- Check if simulation_state is active
SELECT
    is_active,
    simulation_start_time,
    current_simulated_date,
    time_scale
FROM simulation_state;
