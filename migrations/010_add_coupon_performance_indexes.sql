-- ============================================================================
-- Migration 010: Performance Indexes for Coupon Queries
-- Improves coupon application performance by optimizing common queries
-- ============================================================================

-- Index for user_coupons table to speed up eligibility checks
-- Query pattern: WHERE user_id = ? AND eligible_until > NOW()
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_coupons_eligibility
ON user_coupons (user_id, eligible_until DESC, status)
WHERE status = 'active';

-- Index for cart_coupons to speed up selected coupon lookups
-- Query pattern: WHERE user_id = ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cart_coupons_user_created
ON cart_coupons (user_id, created_at DESC);

-- Composite index for coupons table with type and expiration
-- Query pattern: WHERE type = ? AND expiration_date > NOW() AND is_active = true
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_coupons_type_active_expiration
ON coupons (type, is_active, expiration_date)
WHERE is_active = true OR is_active IS NULL;

-- Index for coupon_interactions tracking
-- Query pattern: WHERE user_id = ? AND action = ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_coupon_interactions_user_action
ON coupon_interactions (user_id, action, created_at DESC);

-- Verify indexes were created
DO $$
DECLARE
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE indexname IN (
        'idx_user_coupons_eligibility',
        'idx_cart_coupons_user_created',
        'idx_coupons_type_active_expiration',
        'idx_coupon_interactions_user_action'
    );

    IF index_count = 4 THEN
        RAISE NOTICE '✓ All 4 indexes created successfully';
    ELSE
        RAISE NOTICE '✗ Only % out of 4 indexes created', index_count;
    END IF;
END $$;
