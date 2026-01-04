-- ============================================
-- EVENT TYPES BREAKDOWN
-- Distribution of different event types
-- ============================================

SELECT
    event_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM shopping_session_events), 2) as percentage
FROM shopping_session_events
GROUP BY event_type
ORDER BY count DESC;
