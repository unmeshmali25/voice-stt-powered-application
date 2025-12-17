-- ============================================================================
-- Migration 004: Backfill Coupon Structured Data
-- Run after 002_retail_cart_schema.sql
-- Parses existing discount_details and populates discount_type, discount_value, min_purchase_amount
-- ============================================================================

-- ============================================================================
-- D-15: BACKFILL EXISTING COUPONS
-- Pattern matching to extract structured data from discount_details
-- ============================================================================

-- Pattern: "XX% off" -> percent discount
UPDATE coupons SET
    discount_type = 'percent',
    discount_value = CAST(SUBSTRING(discount_details FROM '(\d+)%') AS DECIMAL),
    is_active = true
WHERE discount_details ~* '\d+%\s*off'
AND discount_type IS NULL;

-- Pattern: "$XX off $YY" -> fixed discount with minimum
UPDATE coupons SET
    discount_type = 'fixed',
    discount_value = CAST(SUBSTRING(discount_details FROM '\$(\d+\.?\d*)\s*off') AS DECIMAL),
    min_purchase_amount = CAST(SUBSTRING(discount_details FROM '\$\d+\.?\d*\s*off\s*\$(\d+\.?\d*)') AS DECIMAL),
    is_active = true
WHERE discount_details ~* '\$\d+\.?\d*\s*off\s*\$\d+'
AND discount_type IS NULL;

-- Pattern: "$XX off" (no minimum) -> fixed discount
UPDATE coupons SET
    discount_type = 'fixed',
    discount_value = CAST(SUBSTRING(discount_details FROM '\$(\d+\.?\d*)\s*off') AS DECIMAL),
    min_purchase_amount = 0,
    is_active = true
WHERE discount_details ~* '\$\d+\.?\d*\s*off'
AND discount_details !~* '\$\d+\.?\d*\s*off\s*\$\d+'
AND discount_type IS NULL;

-- Pattern: "Save $XX" -> fixed discount
UPDATE coupons SET
    discount_type = 'fixed',
    discount_value = CAST(SUBSTRING(discount_details FROM 'Save\s*\$(\d+\.?\d*)') AS DECIMAL),
    min_purchase_amount = 0,
    is_active = true
WHERE discount_details ~* 'Save\s*\$\d+'
AND discount_type IS NULL;

-- Pattern: "Buy X Get Y free" or "Buy X Get Y% off" -> bogo
UPDATE coupons SET
    discount_type = 'bogo',
    discount_value = 100,  -- 100% off the free item
    min_purchase_amount = 0,
    is_active = true
WHERE discount_details ~* 'Buy\s*\d+.*Get\s*\d+\s*free'
AND discount_type IS NULL;

-- Pattern: "Buy X Get Y XX% off" -> bogo with percentage
UPDATE coupons SET
    discount_type = 'bogo',
    discount_value = COALESCE(CAST(SUBSTRING(discount_details FROM 'Get\s*\d+\s*(\d+)%') AS DECIMAL), 50),
    min_purchase_amount = 0,
    is_active = true
WHERE discount_details ~* 'Buy\s*\d+.*Get\s*\d+.*\d+%'
AND discount_type IS NULL;

-- Pattern: "Free shipping" -> free_shipping
UPDATE coupons SET
    discount_type = 'free_shipping',
    discount_value = 0,
    min_purchase_amount = COALESCE(
        CAST(SUBSTRING(discount_details FROM 'over\s*\$(\d+\.?\d*)') AS DECIMAL),
        0
    ),
    is_active = true
WHERE discount_details ~* 'free\s*shipping'
AND discount_type IS NULL;

-- Pattern: "Free X with $YY purchase" -> fixed (treat as $X value)
UPDATE coupons SET
    discount_type = 'fixed',
    discount_value = 5,  -- Assume $5 value for free items
    min_purchase_amount = COALESCE(
        CAST(SUBSTRING(discount_details FROM 'with\s*\$(\d+\.?\d*)') AS DECIMAL),
        0
    ),
    is_active = true
WHERE discount_details ~* 'Free\s+\w+\s+with\s*\$\d+'
AND discount_type IS NULL;

-- Pattern: "Earn double rewards" or other non-discount offers -> percent with 0 (informational)
UPDATE coupons SET
    discount_type = 'percent',
    discount_value = 0,
    min_purchase_amount = 0,
    is_active = true
WHERE discount_details ~* '(earn|double|rewards|points)'
AND discount_type IS NULL;

-- Pattern: "Bundle" deals -> fixed estimate
UPDATE coupons SET
    discount_type = 'fixed',
    discount_value = 5,
    min_purchase_amount = 0,
    is_active = true
WHERE discount_details ~* 'bundle'
AND discount_type IS NULL;

-- Catch-all: Set remaining to percent 10% off as default
UPDATE coupons SET
    discount_type = 'percent',
    discount_value = 10,
    min_purchase_amount = 0,
    is_active = true
WHERE discount_type IS NULL;

-- Set max_discount for high percentage discounts (cap at $50)
UPDATE coupons SET max_discount = 50
WHERE discount_type = 'percent' AND discount_value >= 30 AND max_discount IS NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT
    discount_type,
    COUNT(*) as count,
    AVG(discount_value) as avg_value
FROM coupons
GROUP BY discount_type
ORDER BY count DESC;
