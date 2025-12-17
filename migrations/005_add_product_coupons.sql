-- ============================================================================
-- Migration 005: Add Coupons for Product Categories and Brands
-- Run after 004_backfill_coupons.sql
-- Creates coupons matching the 72 products' categories and brands
-- ============================================================================

-- ============================================================================
-- D-16: NEW CATEGORY COUPONS
-- Categories from products: Baby Care, Beauty, Beverages, Body Wash,
-- Cleaning Products, Detergent, Facewash, First Aid, Health, Kitchen Towels,
-- Laundry, Lip Balm, Paper Products, Personal Care, Sanitary Pads, Serum,
-- Snacks, Sunscreen, Toothbrush, Vitamins
-- ============================================================================

INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms, discount_type, discount_value, min_purchase_amount, is_active) VALUES
-- Beauty (general)
('category', '25% off all Beauty products', 'Beauty', '2026-06-30', 'Excludes prestige brands', 'percent', 25, 0, true),
('category', '$8 off $30 Beauty purchase', 'Beauty', '2026-06-30', NULL, 'fixed', 8, 30, true),
('category', 'Buy 2 Get 1 Free on Beauty essentials', 'Beauty', '2026-03-31', 'Equal or lesser value free', 'bogo', 100, 0, true),

-- Beverages
('category', '20% off all Beverages', 'Beverages', '2026-06-30', NULL, 'percent', 20, 0, true),
('category', '$2 off any Beverage 6-pack or larger', 'Beverages', '2026-06-30', '6-pack minimum', 'fixed', 2, 0, true),
('category', 'Buy 2 Get 1 Free on Energy Drinks', 'Beverages', '2026-03-31', NULL, 'bogo', 100, 0, true),

-- Body Wash
('category', '30% off Body Wash products', 'Body Wash', '2026-06-30', NULL, 'percent', 30, 0, true),
('category', '$3 off any Body Wash', 'Body Wash', '2026-06-30', NULL, 'fixed', 3, 0, true),
('category', 'Buy 1 Get 1 50% off Body Wash', 'Body Wash', '2026-03-31', NULL, 'bogo', 50, 0, true),

-- Cleaning Products
('category', '25% off Cleaning Products', 'Cleaning Products', '2026-06-30', NULL, 'percent', 25, 0, true),
('category', '$5 off $20 Cleaning Products purchase', 'Cleaning Products', '2026-06-30', NULL, 'fixed', 5, 20, true),
('category', 'Buy 2 Get 1 Free on all Cleaners', 'Cleaning Products', '2026-03-31', NULL, 'bogo', 100, 0, true),

-- Detergent
('category', '20% off all Detergent', 'Detergent', '2026-06-30', NULL, 'percent', 20, 0, true),
('category', '$4 off any Laundry Detergent', 'Detergent', '2026-06-30', NULL, 'fixed', 4, 0, true),

-- Facewash
('category', '30% off Facewash products', 'Facewash', '2026-06-30', NULL, 'percent', 30, 0, true),
('category', '$5 off $15 Facewash purchase', 'Facewash', '2026-06-30', NULL, 'fixed', 5, 15, true),

-- Health
('category', '20% off Health products', 'Health', '2026-06-30', 'Excludes prescriptions', 'percent', 20, 0, true),
('category', '$10 off $40 Health purchase', 'Health', '2026-06-30', NULL, 'fixed', 10, 40, true),
('category', 'Buy 1 Get 1 50% off Pain Relief', 'Health', '2026-03-31', NULL, 'bogo', 50, 0, true),

-- Kitchen Towels
('category', '15% off Kitchen Towels', 'Kitchen Towels', '2026-06-30', NULL, 'percent', 15, 0, true),
('category', '$3 off Paper Towels multi-pack', 'Kitchen Towels', '2026-06-30', '6+ rolls', 'fixed', 3, 0, true),

-- Laundry
('category', '25% off Laundry products', 'Laundry', '2026-06-30', NULL, 'percent', 25, 0, true),
('category', '$5 off $25 Laundry purchase', 'Laundry', '2026-06-30', NULL, 'fixed', 5, 25, true),

-- Lip Balm
('category', '30% off Lip Balm', 'Lip Balm', '2026-06-30', NULL, 'percent', 30, 0, true),
('category', 'Buy 2 Get 1 Free on Lip Care', 'Lip Balm', '2026-03-31', NULL, 'bogo', 100, 0, true),

-- Paper Products
('category', '20% off Paper Products', 'Paper Products', '2026-06-30', NULL, 'percent', 20, 0, true),
('category', '$4 off $20 Paper Products purchase', 'Paper Products', '2026-06-30', NULL, 'fixed', 4, 20, true),

-- Sanitary Pads
('category', '25% off Feminine Care', 'Sanitary Pads', '2026-06-30', NULL, 'percent', 25, 0, true),
('category', '$3 off any Sanitary Pads', 'Sanitary Pads', '2026-06-30', NULL, 'fixed', 3, 0, true),

-- Serum
('category', '20% off all Serums', 'Serum', '2026-06-30', NULL, 'percent', 20, 0, true),
('category', '$10 off $35 Serum purchase', 'Serum', '2026-06-30', 'Premium skincare', 'fixed', 10, 35, true),

-- Snacks
('category', '25% off Snacks', 'Snacks', '2026-06-30', NULL, 'percent', 25, 0, true),
('category', 'Buy 2 Get 1 Free on Snacks', 'Snacks', '2026-03-31', NULL, 'bogo', 100, 0, true),
('category', '$2 off any Snack item', 'Snacks', '2026-06-30', NULL, 'fixed', 2, 0, true),

-- Sunscreen
('category', '30% off Sunscreen', 'Sunscreen', '2026-06-30', 'SPF 30+', 'percent', 30, 0, true),
('category', '$5 off $20 Sunscreen purchase', 'Sunscreen', '2026-06-30', NULL, 'fixed', 5, 20, true),
('category', 'Buy 1 Get 1 50% off Sun Protection', 'Sunscreen', '2026-03-31', NULL, 'bogo', 50, 0, true),

-- Toothbrush
('category', '25% off Toothbrushes', 'Toothbrush', '2026-06-30', NULL, 'percent', 25, 0, true),
('category', '$2 off any Manual Toothbrush', 'Toothbrush', '2026-06-30', NULL, 'fixed', 2, 0, true);

-- ============================================================================
-- D-16: NEW BRAND COUPONS
-- Brands from products not already covered in staging seed
-- ============================================================================

INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms, discount_type, discount_value, min_purchase_amount, is_active) VALUES
-- Pain Relief & Health Brands
('brand', '$2 off Aleve pain relief', 'Aleve', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$1.50 off Motrin products', 'Motrin', '2026-06-30', NULL, 'fixed', 1.50, 0, true),
('brand', '$2 off Sudafed cold & flu', 'Sudafed', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$1 off Neosporin first aid', 'Neosporin', '2026-06-30', NULL, 'fixed', 1, 0, true),
('brand', '$1 off Polysporin antibiotic', 'Polysporin', '2026-06-30', NULL, 'fixed', 1, 0, true),
('brand', '$2 off Band-Aid products', 'Band-Aid', '2026-06-30', NULL, 'fixed', 2, 0, true),

-- CVS Store Brands
('brand', '30% off CVS Health products', 'CVS Health', '2026-06-30', 'Store brand savings', 'percent', 30, 0, true),
('brand', '25% off CVS brand items', 'CVS', '2026-06-30', NULL, 'percent', 25, 0, true),
('brand', '$3 off One+other products', 'One+other', '2026-06-30', NULL, 'fixed', 3, 0, true),

-- Skincare Brands
('brand', '20% off The Ordinary skincare', 'The Ordinary', '2026-06-30', NULL, 'percent', 20, 0, true),
('brand', '$8 off Glow Recipe products', 'Glow Recipe', '2026-06-30', NULL, 'fixed', 8, 0, true),
('brand', '$5 off EltaMD sunscreen', 'EltaMD', '2026-06-30', NULL, 'fixed', 5, 0, true),
('brand', '$4 off Nécessaire body care', 'Nécessaire', '2026-06-30', NULL, 'fixed', 4, 0, true),
('brand', '$3 off Clean & Clear products', 'Clean & Clear', '2026-06-30', NULL, 'fixed', 3, 0, true),

-- Sunscreen Brands
('brand', '$3 off Banana Boat sunscreen', 'Banana Boat', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$3 off Coppertone sun care', 'Coppertone', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$4 off Hawaiian Tropic products', 'Hawaiian Tropic', '2026-06-30', NULL, 'fixed', 4, 0, true),
('brand', '$4 off Sun Bum sunscreen', 'Sun Bum', '2026-06-30', NULL, 'fixed', 4, 0, true),

-- Lip Care Brands
('brand', '$1 off Blistex lip care', 'Blistex', '2026-06-30', NULL, 'fixed', 1, 0, true),
('brand', '$1 off Carmex lip balm', 'Carmex', '2026-06-30', NULL, 'fixed', 1, 0, true),
('brand', '$1.50 off EOS lip products', 'EOS', '2026-06-30', NULL, 'fixed', 1.50, 0, true),

-- Cosmetics Brands
('brand', '30% off NYX Professional Makeup', 'NYX Professional', '2026-06-30', NULL, 'percent', 30, 0, true),
('brand', '25% off Wet n Wild cosmetics', 'Wet n Wild', '2026-06-30', NULL, 'percent', 25, 0, true),
('brand', '$3 off Essence makeup', 'Essence', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$4 off Physician''s Formula', 'Physician''s Formula', '2026-06-30', NULL, 'fixed', 4, 0, true),
('brand', '25% off Rimmel London makeup', 'Rimmel London', '2026-06-30', NULL, 'percent', 25, 0, true),

-- Baby Care Brands
('brand', '$2 off Johnson''s Baby products', 'Johnson''s Baby', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$3 off Desitin diaper cream', 'Desitin', '2026-06-30', NULL, 'fixed', 3, 0, true),

-- Personal Care Brands
('brand', '$2 off Always feminine care', 'Always', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$2 off Secret deodorant', 'Secret', '2026-06-30', NULL, 'fixed', 2, 0, true),

-- Paper & Cleaning Brands
('brand', '$3 off Bounty paper towels', 'Bounty', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$2 off Kleenex tissues', 'Kleenex', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$3 off Quilted Northern toilet paper', 'Quilted Northern', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$2 off Scott paper products', 'Scott', '2026-06-30', NULL, 'fixed', 2, 0, true),

-- Cleaning Products Brands
('brand', '$2 off Lysol cleaners', 'Lysol', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$3 off Clorox products', 'Clorox', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$2 off Mr. Clean products', 'Mr. Clean', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$2 off Windex glass cleaner', 'Windex', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$2 off Scrubbing Bubbles', 'Scrubbing Bubbles', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$3 off Method cleaners', 'Method', '2026-06-30', NULL, 'fixed', 3, 0, true),

-- Laundry Brands
('brand', '$3 off Tide laundry detergent', 'Tide', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$2 off Arm & Hammer laundry', 'Arm & Hammer', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$3 off OxiClean stain remover', 'OxiClean', '2026-06-30', NULL, 'fixed', 3, 0, true),
('brand', '$2 off Shout stain remover', 'Shout', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$2 off Woolite detergent', 'Woolite', '2026-06-30', NULL, 'fixed', 2, 0, true),

-- Beverage Brands
('brand', '$2 off Red Bull energy drinks', 'Red Bull', '2026-06-30', '4-pack or larger', 'fixed', 2, 0, true),
('brand', '$1 off Gatorade sports drinks', 'Gatorade', '2026-06-30', NULL, 'fixed', 1, 0, true),
('brand', '$1 off Fiji water', 'Fiji', '2026-06-30', NULL, 'fixed', 1, 0, true),

-- Snack Brands
('brand', '$2 off Planters nuts', 'Planters', '2026-06-30', NULL, 'fixed', 2, 0, true),
('brand', '$1 off Nature Valley bars', 'Nature Valley', '2026-06-30', NULL, 'fixed', 1, 0, true),

-- Vitamin Brands (additional)
('brand', '$4 off Nature''s Truth vitamins', 'Nature''s Truth', '2026-06-30', NULL, 'fixed', 4, 0, true),
('brand', '$5 off Nature Made supplements', 'Nature Made', '2026-06-30', NULL, 'fixed', 5, 0, true),

-- Oral Care
('brand', '$2 off Oral-B toothbrushes', 'Oral-B', '2026-06-30', NULL, 'fixed', 2, 0, true);

-- ============================================================================
-- ADDITIONAL FRONTSTORE COUPONS FOR CART TESTING
-- ============================================================================
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms, discount_type, discount_value, min_purchase_amount, max_discount, is_active) VALUES
('frontstore', '10% off orders over $25', NULL, '2026-06-30', 'Minimum $25 purchase required', 'percent', 10, 25, 25, true),
('frontstore', '15% off orders over $50', NULL, '2026-06-30', 'Minimum $50 purchase required', 'percent', 15, 50, 50, true),
('frontstore', '$15 off $75 purchase', NULL, '2026-06-30', 'Excludes prescriptions', 'fixed', 15, 75, NULL, true),
('frontstore', '$25 off $125 purchase', NULL, '2026-06-30', 'One per customer', 'fixed', 25, 125, NULL, true),
('frontstore', 'Free shipping on orders over $25', NULL, '2026-06-30', 'Standard shipping only', 'free_shipping', 0, 25, NULL, true);

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT
    'Total coupons:' as info,
    COUNT(*) as count
FROM coupons
UNION ALL
SELECT 'Frontstore:', COUNT(*) FROM coupons WHERE type = 'frontstore'
UNION ALL
SELECT 'Category:', COUNT(*) FROM coupons WHERE type = 'category'
UNION ALL
SELECT 'Brand:', COUNT(*) FROM coupons WHERE type = 'brand'
UNION ALL
SELECT 'With structured data:', COUNT(*) FROM coupons WHERE discount_type IS NOT NULL;
