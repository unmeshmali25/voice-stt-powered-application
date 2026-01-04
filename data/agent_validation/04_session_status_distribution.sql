-- ============================================
-- SESSION STATUS DISTRIBUTION
-- Breakdown of session statuses
-- ============================================

SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM shopping_sessions), 2) as percentage
FROM shopping_sessions
GROUP BY status
ORDER BY count DESC;
