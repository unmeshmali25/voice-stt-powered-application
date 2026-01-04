-- ============================================
-- BASIC METRIC COUNTS
-- Individual validation queries for each metric
-- ============================================

-- 1. AGENTS PROCESSED (Expected: 2400)
SELECT
    'Agents Processed' as metric,
    COUNT(*) as actual,
    2400 as expected,
    COUNT(*) = 2400 as matches
FROM agents
WHERE is_active = true;

-- 2. AGENTS SHOPPED (Expected: 1010)
SELECT
    'Agents Shopped' as metric,
    COUNT(DISTINCT user_id) as actual,
    1010 as expected,
    COUNT(DISTINCT user_id) = 1010 as matches
FROM shopping_sessions;

-- 3. SESSIONS CREATED (Expected: 1010)
SELECT
    'Sessions Created' as metric,
    COUNT(*) as actual,
    1010 as expected,
    COUNT(*) = 1010 as matches
FROM shopping_sessions;

-- 4. CHECKOUTS (Expected: 539)
SELECT
    'Checkouts' as metric,
    COUNT(*) as actual,
    539 as expected,
    COUNT(*) = 539 as matches
FROM shopping_sessions
WHERE status = 'completed';

-- 5. ABANDONED (Expected: 471)
SELECT
    'Abandoned' as metric,
    COUNT(*) as actual,
    471 as expected,
    COUNT(*) = 471 as matches
FROM shopping_sessions
WHERE status = 'abandoned';

-- 6. EVENTS CREATED (Expected: 6598)
SELECT
    'Events Created' as metric,
    COUNT(*) as actual,
    6598 as expected,
    COUNT(*) = 6598 as matches
FROM shopping_session_events;

-- 7. OFFERS ASSIGNED (Expected: 1568)
SELECT
    'Offers Assigned' as metric,
    COUNT(*) as actual,
    1568 as expected,
    COUNT(*) = 1568 as matches
FROM user_coupons
WHERE is_simulation = true;
