-- Sprint 1, Task 1.1: Fix Coupon Linkage
-- Migration: Add order_id and redeemed_at columns, backfill coupon usage data

-- Step 1: Add new columns to user_coupons table
ALTER TABLE user_coupons
    ADD COLUMN IF NOT EXISTS order_id UUID REFERENCES orders(id),
    ADD COLUMN IF NOT EXISTS redeemed_at TIMESTAMP WITH TIME ZONE;

-- Add index for efficient joins
CREATE INDEX IF NOT EXISTS idx_user_coupons_order_id ON user_coupons(order_id);
CREATE INDEX IF NOT EXISTS idx_user_coupons_redeemed_at ON user_coupons(redeemed_at);

-- Step 2: Update status to 'used' where coupons were applied in orders
-- First, identify which coupons were actually used in orders
WITH used_coupons AS (
    SELECT DISTINCT
        o.id as order_id,
        o.user_id,
        oi.applied_coupon_id as coupon_id,
        o.order_date as redeemed_at
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE oi.applied_coupon_id IS NOT NULL
)
UPDATE user_coupons uc
SET 
    status = 'used',
    order_id = uc_order.order_id,
    redeemed_at = uc_order.redeemed_at
FROM used_coupons uc_order
WHERE uc.user_id = uc_order.user_id
  AND uc.coupon_id = uc_order.coupon_id
  AND uc.status != 'used';

-- Step 3: Validation queries (run these separately to verify)
-- Count of coupons marked as used
-- SELECT COUNT(*) as used_coupon_count FROM user_coupons WHERE status = 'used';

-- Verify linkage between user_coupons and orders
-- SELECT 
--     COUNT(*) as linked_coupons,
--     COUNT(DISTINCT uc.order_id) as unique_orders_with_coupons
-- FROM user_coupons uc
-- WHERE uc.order_id IS NOT NULL;

-- Check for any orphaned used coupons (should be 0)
-- SELECT COUNT(*) as orphaned_count
-- FROM user_coupons uc
-- WHERE uc.status = 'used' 
--   AND uc.order_id IS NULL;
