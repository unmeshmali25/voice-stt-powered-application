-- ============================================
-- COUPON STATUS BREAKDOWN
-- Distribution of coupon statuses (simulation only)
-- ============================================

SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM user_coupons WHERE is_simulation = true), 2) as percentage
FROM user_coupons
WHERE is_simulation = true
GROUP BY status
ORDER BY count DESC;
