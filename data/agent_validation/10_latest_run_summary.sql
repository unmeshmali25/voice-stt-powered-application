-- ============================================
-- LATEST SIMULATION RUN SUMMARY
-- Validates metrics for the most recent simulation run only
-- ============================================

-- First, identify the latest simulation time window
WITH latest_run AS (
    SELECT
        MAX(started_at) as latest_start
    FROM shopping_sessions
    WHERE is_simulated = true
),
time_window AS (
    SELECT
        latest_start,
        latest_start - INTERVAL '2 hours' as window_start
    FROM latest_run
)
SELECT
    'Latest Run Time Window' as info,
    TO_CHAR(window_start, 'YYYY-MM-DD HH24:MI:SS') as from_time,
    TO_CHAR(latest_start, 'YYYY-MM-DD HH24:MI:SS') as to_time
FROM time_window
UNION ALL
SELECT
    'Agents Processed',
    (SELECT COUNT(DISTINCT a.user_id)::text
     FROM agents a
     JOIN shopping_sessions ss ON ss.user_id = a.user_id
     WHERE ss.started_at >= (SELECT window_start FROM time_window)),
    ''
UNION ALL
SELECT
    'Agents Shopped',
    (SELECT COUNT(DISTINCT user_id)::text
     FROM shopping_sessions
     WHERE started_at >= (SELECT window_start FROM time_window)),
    ''
UNION ALL
SELECT
    'Sessions Created',
    (SELECT COUNT(*)::text
     FROM shopping_sessions
     WHERE started_at >= (SELECT window_start FROM time_window)),
    ''
UNION ALL
SELECT
    'Checkouts',
    (SELECT COUNT(*)::text
     FROM shopping_sessions
     WHERE status = 'completed'
       AND started_at >= (SELECT window_start FROM time_window)),
    ''
UNION ALL
SELECT
    'Abandoned',
    (SELECT COUNT(*)::text
     FROM shopping_sessions
     WHERE status = 'abandoned'
       AND started_at >= (SELECT window_start FROM time_window)),
    ''
UNION ALL
SELECT
    'Events Created',
    (SELECT COUNT(*)::text
     FROM shopping_session_events
     WHERE created_at >= (SELECT window_start FROM time_window)),
    '';
