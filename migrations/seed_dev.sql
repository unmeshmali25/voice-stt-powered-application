-- Development Seed Data for VoiceOffers
-- This file contains sample coupons for local testing
-- Run after postgres_schema.sql

-- Clear existing data (development only!)
DELETE FROM coupon_usage;
DELETE FROM user_coupons;
DELETE FROM coupons;
DELETE FROM user_attributes;
DELETE FROM users WHERE email LIKE '%@example.com';

-- Sample users (for manual testing)
-- Note: In production, users are synced from Supabase Auth automatically
INSERT INTO users (id, email, full_name) VALUES
('00000000-0000-0000-0000-000000000001', 'alice@example.com', 'Alice Developer'),
('00000000-0000-0000-0000-000000000002', 'bob@example.com', 'Bob Tester')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- FRONTSTORE COUPONS (store-wide offers)
-- ============================================================================
INSERT INTO coupons (id, type, discount_details, category_or_brand, expiration_date, terms) VALUES
('10000000-0000-0000-0000-000000000001', 'frontstore', '20% off your entire purchase', NULL, '2025-12-31', 'Excludes sale items and prescriptions'),
('10000000-0000-0000-0000-000000000002', 'frontstore', '$10 off $50 purchase', NULL, '2025-12-31', 'One-time use only'),
('10000000-0000-0000-0000-000000000003', 'frontstore', 'Free shipping on orders over $35', NULL, '2025-12-31', 'Online orders only'),
('10000000-0000-0000-0000-000000000004', 'frontstore', 'Buy 2, get 1 free on select items', NULL, '2025-11-30', 'Equal or lesser value')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- CATEGORY COUPONS (product category specific)
-- ============================================================================
INSERT INTO coupons (id, type, discount_details, category_or_brand, expiration_date, terms) VALUES
-- Health & Wellness
('20000000-0000-0000-0000-000000000001', 'category', 'Buy 1 Get 1 50% off all vitamins', 'vitamins', '2025-12-31', 'Lower priced item 50% off'),
('20000000-0000-0000-0000-000000000002', 'category', '30% off all vitamins and supplements', 'vitamins', '2025-12-31', NULL),
('20000000-0000-0000-0000-000000000003', 'category', '$5 off $25 vitamins purchase', 'vitamins', '2025-12-31', NULL),

-- Skincare
('20000000-0000-0000-0000-000000000004', 'category', '30% off skincare products', 'skincare', '2025-12-31', 'Excludes premium brands'),
('20000000-0000-0000-0000-000000000005', 'category', 'Buy 2 Get 1 free on facial skincare', 'skincare', '2025-11-30', NULL),
('20000000-0000-0000-0000-000000000006', 'category', '$10 off $40 skincare purchase', 'skincare', '2025-12-31', NULL),

-- Hair Care
('20000000-0000-0000-0000-000000000007', 'category', '25% off all hair care products', 'hair care', '2025-12-31', NULL),
('20000000-0000-0000-0000-000000000008', 'category', 'Buy 2 Get 1 free on shampoo and conditioner', 'hair care', '2025-11-30', NULL),

-- Cosmetics
('20000000-0000-0000-0000-000000000009', 'category', '40% off all makeup and cosmetics', 'cosmetics', '2025-12-31', 'While supplies last'),
('20000000-0000-0000-0000-000000000010', 'category', 'Free lipstick with $30 cosmetics purchase', 'cosmetics', '2025-11-30', NULL),

-- Baby & Kids
('20000000-0000-0000-0000-000000000011', 'category', '20% off baby care products', 'baby care', '2025-12-31', NULL),
('20000000-0000-0000-0000-000000000012', 'category', '$5 off $25 baby formula', 'baby care', '2025-12-31', NULL),

-- Personal Care
('20000000-0000-0000-0000-000000000013', 'category', 'Buy 1 Get 1 50% off deodorants', 'personal care', '2025-12-31', NULL),
('20000000-0000-0000-0000-000000000014', 'category', '25% off oral care products', 'oral care', '2025-12-31', 'Toothpaste, mouthwash, brushes')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- BRAND COUPONS (specific manufacturers)
-- ============================================================================
INSERT INTO coupons (id, type, discount_details, category_or_brand, expiration_date, terms) VALUES
-- Popular health brands
('30000000-0000-0000-0000-000000000001', 'brand', '$2 off any Centrum multivitamin', 'Centrum', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000002', 'brand', '$5 off $20 Nature Made vitamins', 'Nature Made', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000003', 'brand', 'Save $3 on Emergen-C products', 'Emergen-C', '2025-12-31', NULL),

-- Skincare brands
('30000000-0000-0000-0000-000000000004', 'brand', '$5 off $20 Neutrogena skincare', 'Neutrogena', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000005', 'brand', '$2 off Dove body wash or lotion', 'Dove', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000006', 'brand', '30% off all CeraVe products', 'CeraVe', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000007', 'brand', 'Buy 2 Get 1 free on Olay products', 'Olay', '2025-11-30', NULL),

-- Hair care brands
('30000000-0000-0000-0000-000000000008', 'brand', '$3 off Pantene shampoo or conditioner', 'Pantene', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000009', 'brand', 'Save $2 on any Herbal Essences product', 'Herbal Essences', '2025-12-31', NULL),

-- Cosmetics brands
('30000000-0000-0000-0000-000000000010', 'brand', '40% off all Maybelline cosmetics', 'Maybelline', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000011', 'brand', 'Buy 1 Get 1 50% off L\'Oreal makeup', 'L\'Oreal', '2025-11-30', NULL),
('30000000-0000-0000-0000-000000000012', 'brand', '$5 off $25 Revlon products', 'Revlon', '2025-12-31', NULL),

-- Baby brands
('30000000-0000-0000-0000-000000000013', 'brand', '$3 off Pampers diapers', 'Pampers', '2025-12-31', 'Size 3 or larger'),
('30000000-0000-0000-0000-000000000014', 'brand', 'Save $2 on Huggies wipes', 'Huggies', '2025-12-31', NULL),

-- Oral care brands
('30000000-0000-0000-0000-000000000015', 'brand', '$1.50 off Colgate toothpaste', 'Colgate', '2025-12-31', NULL),
('30000000-0000-0000-0000-000000000016', 'brand', '$5 off Philips Sonicare brush', 'Philips Sonicare', '2025-12-31', NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- ASSIGN RANDOM COUPONS TO TEST USERS
-- ============================================================================
-- Alice gets a mix of coupons (15-20 coupons)
WITH random_coupons AS (
    SELECT id FROM coupons ORDER BY RANDOM() LIMIT 18
)
INSERT INTO user_coupons (user_id, coupon_id, eligible_until)
SELECT '00000000-0000-0000-0000-000000000001', id, '2025-12-31 23:59:59'
FROM random_coupons
ON CONFLICT (user_id, coupon_id) DO NOTHING;

-- Bob gets a different mix (10-15 coupons)
WITH random_coupons AS (
    SELECT id FROM coupons WHERE type IN ('frontstore', 'brand') ORDER BY RANDOM() LIMIT 12
)
INSERT INTO user_coupons (user_id, coupon_id, eligible_until)
SELECT '00000000-0000-0000-0000-000000000002', id, '2025-12-31 23:59:59'
FROM random_coupons
ON CONFLICT (user_id, coupon_id) DO NOTHING;

-- Verification queries
SELECT 'Coupons created:' as info, COUNT(*) as count FROM coupons
UNION ALL
SELECT 'Users created:', COUNT(*) FROM users WHERE email LIKE '%@example.com'
UNION ALL
SELECT 'User-coupon assignments:', COUNT(*) FROM user_coupons;

-- Show sample assignments
SELECT u.email, COUNT(uc.coupon_id) as assigned_coupons
FROM users u
LEFT JOIN user_coupons uc ON u.id = uc.user_id
WHERE u.email LIKE '%@example.com'
GROUP BY u.email;
