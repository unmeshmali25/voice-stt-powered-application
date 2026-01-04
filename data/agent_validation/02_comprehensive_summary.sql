-- ============================================
-- COMPREHENSIVE SUMMARY
-- All metrics in a single unified view
-- ============================================

SELECT
    'Agents Processed' as metric,
    (SELECT COUNT(*) FROM agents WHERE is_active = true) as actual,
    2400 as expected,
    (SELECT COUNT(*) FROM agents WHERE is_active = true) = 2400 as matches
UNION ALL
SELECT
    'Agents Shopped',
    (SELECT COUNT(DISTINCT user_id) FROM shopping_sessions),
    1010,
    (SELECT COUNT(DISTINCT user_id) FROM shopping_sessions) = 1010
UNION ALL
SELECT
    'Sessions Created',
    (SELECT COUNT(*) FROM shopping_sessions),
    1010,
    (SELECT COUNT(*) FROM shopping_sessions) = 1010
UNION ALL
SELECT
    'Checkouts',
    (SELECT COUNT(*) FROM shopping_sessions WHERE status = 'completed'),
    539,
    (SELECT COUNT(*) FROM shopping_sessions WHERE status = 'completed') = 539
UNION ALL
SELECT
    'Abandoned',
    (SELECT COUNT(*) FROM shopping_sessions WHERE status = 'abandoned'),
    471,
    (SELECT COUNT(*) FROM shopping_sessions WHERE status = 'abandoned') = 471
UNION ALL
SELECT
    'Events Created',
    (SELECT COUNT(*) FROM shopping_session_events),
    6598,
    (SELECT COUNT(*) FROM shopping_session_events) = 6598
UNION ALL
SELECT
    'Offers Assigned',
    (SELECT COUNT(*) FROM user_coupons WHERE is_simulation = true),
    1568,
    (SELECT COUNT(*) FROM user_coupons WHERE is_simulation = true) = 1568;
