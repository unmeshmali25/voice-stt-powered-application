-- Staging Seed Data for VoiceOffers
-- This file contains realistic test data for staging environment testing
-- More coupons than dev, simulates production-like data
-- Run after postgres_schema.sql

-- Note: Users in staging come from Supabase Auth, not seeded here
-- This script only creates coupons that can be assigned to test users

-- Clear existing coupons (staging only!)
DELETE FROM coupon_usage;
DELETE FROM user_coupons;
DELETE FROM coupons;

-- ============================================================================
-- FRONTSTORE COUPONS (10 store-wide offers)
-- ============================================================================
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('frontstore', '20% off your entire purchase', NULL, '2026-03-31', 'Excludes sale items and prescriptions. One-time use.'),
('frontstore', '$10 off $50 purchase', NULL, '2026-03-31', 'One-time use only. Cannot be combined with other offers.'),
('frontstore', 'Free shipping on orders over $35', NULL, '2026-03-31', 'Online orders only. Standard shipping.'),
('frontstore', 'Buy 2, get 1 free on select items', NULL, '2026-02-28', 'Equal or lesser value. Excludes prescriptions.'),
('frontstore', '$5 off $25 purchase', NULL, '2026-03-31', 'In-store and online.'),
('frontstore', '15% off first online order', NULL, '2026-03-31', 'New customers only. Enter code at checkout.'),
('frontstore', 'Earn double rewards points this week', NULL, '2026-01-31', 'Rewards members only. Excludes gift cards.'),
('frontstore', '$20 off $100 purchase', NULL, '2026-03-31', 'Excludes prescriptions and alcohol.'),
('frontstore', 'Free gift with $75 purchase', NULL, '2026-02-14', 'While supplies last. Valentine''s Day special.'),
('frontstore', '25% off clearance items', NULL, '2026-01-31', 'Final sale. No returns.');

-- ============================================================================
-- CATEGORY COUPONS (50+ category-specific offers)
-- ============================================================================

-- Vitamins & Supplements (15 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('category', 'Buy 1 Get 1 50% off all vitamins', 'vitamins', '2026-03-31', 'Lower priced item 50% off. Cannot combine.'),
('category', '30% off all vitamins and supplements', 'vitamins', '2026-03-31', 'Excludes protein powders.'),
('category', '$5 off $25 vitamins purchase', 'vitamins', '2026-03-31', NULL),
('category', 'Buy 2 Get 1 free on multivitamins', 'vitamins', '2026-02-28', 'Equal or lesser value.'),
('category', '$10 off $50 supplement purchase', 'vitamins', '2026-03-31', NULL),
('category', '40% off select vitamins', 'vitamins', '2026-01-31', 'See store for details.'),
('category', 'Free vitamin D with $30 purchase', 'vitamins', '2026-03-31', 'While supplies last.'),
('category', 'Save up to $15 on omega-3', 'vitamins', '2026-03-31', NULL),
('category', '25% off probiotics', 'vitamins', '2026-03-31', NULL),
('category', 'Buy 3 Get 1 free on gummy vitamins', 'vitamins', '2026-02-28', NULL),
('category', '$8 off vitamin subscription', 'vitamins', '2026-03-31', 'Auto-delivery required.'),
('category', '50% off second bottle of same vitamin', 'vitamins', '2026-03-31', NULL),
('category', 'Free shipping on vitamin orders over $25', 'vitamins', '2026-03-31', 'Online only.'),
('category', '$3 off children''s vitamins', 'vitamins', '2026-03-31', NULL),
('category', 'Bundle deal: Vitamin C + D for $15', 'vitamins', '2026-02-28', 'Limited time offer.');

-- Skincare (15 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('category', '30% off skincare products', 'skincare', '2026-03-31', 'Excludes premium and prestige brands.'),
('category', 'Buy 2 Get 1 free on facial skincare', 'skincare', '2026-02-28', 'Equal or lesser value.'),
('category', '$10 off $40 skincare purchase', 'skincare', '2026-03-31', NULL),
('category', '40% off anti-aging serums', 'skincare', '2026-03-31', NULL),
('category', 'Free moisturizer with $50 skincare purchase', 'skincare', '2026-02-14', 'While supplies last.'),
('category', '25% off acne treatment products', 'skincare', '2026-03-31', NULL),
('category', '$5 off $20 facial cleansers', 'skincare', '2026-03-31', NULL),
('category', 'Buy 1 Get 1 50% off sunscreen', 'skincare', '2026-03-31', 'SPF 30 or higher.'),
('category', '35% off skincare gift sets', 'skincare', '2026-02-28', 'Perfect for Valentine''s Day.'),
('category', '$15 off luxury skincare', 'skincare', '2026-03-31', 'Brands: La Roche-Posay, Vichy, CeraVe.'),
('category', 'Free travel-size product with purchase', 'skincare', '2026-03-31', '$25 minimum purchase.'),
('category', '50% off second skincare item', 'skincare', '2026-03-31', 'Add 2 to cart for discount.'),
('category', 'Buy 3 sheet masks, get 3 free', 'skincare', '2026-02-28', NULL),
('category', '$20 off skincare devices', 'skincare', '2026-03-31', 'Cleansing brushes, LED masks.'),
('category', '30% off men''s skincare', 'skincare', '2026-03-31', NULL);

-- Hair Care (12 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('category', '25% off all hair care products', 'hair care', '2026-03-31', NULL),
('category', 'Buy 2 Get 1 free on shampoo and conditioner', 'hair care', '2026-02-28', 'Equal or lesser value.'),
('category', '$4 off any hair styling product', 'hair care', '2026-03-31', 'Gels, mousses, sprays.'),
('category', '30% off salon hair care brands', 'hair care', '2026-03-31', NULL),
('category', 'Buy 1 Get 1 50% off hair treatments', 'hair care', '2026-03-31', 'Masks, oils, leave-in treatments.'),
('category', '$10 off $30 hair care purchase', 'hair care', '2026-03-31', NULL),
('category', 'Free hair serum with $25 purchase', 'hair care', '2026-02-28', 'While supplies last.'),
('category', '40% off hair color products', 'hair care', '2026-03-31', NULL),
('category', '$5 off professional hair tools', 'hair care', '2026-03-31', 'Brushes, combs, clips.'),
('category', '25% off natural hair care', 'hair care', '2026-03-31', 'Sulfate-free, paraben-free.'),
('category', 'Bundle: Shampoo + conditioner for $18', 'hair care', '2026-02-28', NULL),
('category', '50% off travel-size hair products', 'hair care', '2026-03-31', 'Perfect for trips.');

-- Cosmetics (12 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('category', '40% off all makeup and cosmetics', 'cosmetics', '2026-03-31', 'While supplies last. Select brands.'),
('category', 'Free lipstick with $30 cosmetics purchase', 'cosmetics', '2026-02-14', 'Valentine''s special.'),
('category', 'Buy 2 Get 1 free on nail polish', 'cosmetics', '2026-02-28', NULL),
('category', '$10 off $40 makeup purchase', 'cosmetics', '2026-03-31', NULL),
('category', '50% off second makeup item', 'cosmetics', '2026-03-31', 'Equal or lesser value.'),
('category', '30% off lip products', 'cosmetics', '2026-03-31', 'Lipsticks, glosses, liners.'),
('category', '$5 off eye makeup palettes', 'cosmetics', '2026-03-31', NULL),
('category', 'Free makeup bag with $50 purchase', 'cosmetics', '2026-02-28', 'While supplies last.'),
('category', '25% off makeup brushes and tools', 'cosmetics', '2026-03-31', NULL),
('category', 'Buy 1 Get 1 50% off foundation', 'cosmetics', '2026-03-31', NULL),
('category', '$15 off premium makeup brands', 'cosmetics', '2026-03-31', 'IT Cosmetics, Clinique, Estée Lauder.'),
('category', '35% off makeup gift sets', 'cosmetics', '2026-02-28', NULL);

-- Baby Care (10 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('category', '20% off baby care products', 'baby care', '2026-03-31', NULL),
('category', '$5 off $25 baby formula', 'baby care', '2026-03-31', NULL),
('category', 'Buy 2 boxes diapers, get $10 off', 'baby care', '2026-03-31', NULL),
('category', '$3 off baby wipes', 'baby care', '2026-03-31', 'Any size.'),
('category', 'Free baby lotion with $30 purchase', 'baby care', '2026-02-28', NULL),
('category', '25% off baby feeding supplies', 'baby care', '2026-03-31', 'Bottles, nipples, bibs.'),
('category', '$10 off baby gear', 'baby care', '2026-03-31', 'Monitors, thermometers, safety items.'),
('category', 'Buy 1 Get 1 50% off baby bath products', 'baby care', '2026-03-31', NULL),
('category', '30% off newborn essentials bundle', 'baby care', '2026-02-28', NULL),
('category', '$15 off baby formula subscription', 'baby care', '2026-03-31', 'Auto-delivery.');

-- Additional categories (Personal Care, Oral Care, Nutrition, First Aid)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('category', 'Buy 1 Get 1 50% off deodorants', 'personal care', '2026-03-31', NULL),
('category', '$3 off body wash or soap', 'personal care', '2026-03-31', NULL),
('category', '25% off shaving products', 'personal care', '2026-03-31', 'Razors, creams, aftershave.'),
('category', '$5 off feminine care products', 'personal care', '2026-03-31', NULL),
('category', '25% off oral care products', 'oral care', '2026-03-31', 'Toothpaste, mouthwash, floss.'),
('category', '$1.50 off any toothpaste', 'oral care', '2026-03-31', NULL),
('category', 'Free toothbrush with $15 oral care purchase', 'oral care', '2026-02-28', NULL),
('category', '$10 off electric toothbrush', 'oral care', '2026-03-31', NULL),
('category', '30% off protein bars and shakes', 'nutrition', '2026-03-31', NULL),
('category', '$5 off meal replacement shakes', 'nutrition', '2026-03-31', NULL),
('category', '25% off first aid supplies', 'first aid', '2026-03-31', 'Bandages, ointments, tape.'),
('category', '$3 off pain relief products', 'first aid', '2026-03-31', 'Aspirin, ibuprofen, acetaminophen.');

-- ============================================================================
-- BRAND COUPONS (50+ brand-specific offers)
-- ============================================================================

-- Health & Wellness Brands (12 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('brand', '$2 off any Centrum multivitamin', 'Centrum', '2026-03-31', NULL),
('brand', '$5 off $20 Nature Made vitamins', 'Nature Made', '2026-03-31', NULL),
('brand', 'Save $3 on Emergen-C products', 'Emergen-C', '2026-03-31', '10-count or larger.'),
('brand', '$4 off One A Day vitamins', 'One A Day', '2026-03-31', NULL),
('brand', '$6 off Caltrate calcium supplement', 'Caltrate', '2026-03-31', NULL),
('brand', 'Buy 2 Get 1 free on Vitafusion gummies', 'Vitafusion', '2026-02-28', NULL),
('brand', '$3 off Nature''s Bounty supplements', 'Nature''s Bounty', '2026-03-31', NULL),
('brand', '$5 off GNC vitamins', 'GNC', '2026-03-31', NULL),
('brand', 'Save $2 on Airborne products', 'Airborne', '2026-03-31', NULL),
('brand', '$4 off Garden of Life supplements', 'Garden of Life', '2026-03-31', 'Organic products.'),
('brand', '$3 off Rainbow Light vitamins', 'Rainbow Light', '2026-03-31', NULL),
('brand', '$5 off MegaFood supplements', 'MegaFood', '2026-03-31', NULL);

-- Skincare Brands (15 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('brand', '$5 off $20 Neutrogena skincare', 'Neutrogena', '2026-03-31', NULL),
('brand', '$2 off Dove body wash or lotion', 'Dove', '2026-03-31', NULL),
('brand', '30% off all CeraVe products', 'CeraVe', '2026-03-31', NULL),
('brand', 'Buy 2 Get 1 free on Olay products', 'Olay', '2026-02-28', NULL),
('brand', '$4 off Cetaphil cleanser or moisturizer', 'Cetaphil', '2026-03-31', NULL),
('brand', '$10 off La Roche-Posay skincare', 'La Roche-Posay', '2026-03-31', NULL),
('brand', '$3 off Aveeno products', 'Aveeno', '2026-03-31', NULL),
('brand', '$5 off Eucerin skincare', 'Eucerin', '2026-03-31', NULL),
('brand', '25% off Garnier skincare', 'Garnier', '2026-03-31', NULL),
('brand', '$6 off RoC anti-aging products', 'RoC', '2026-03-31', NULL),
('brand', '$4 off Simple skincare', 'Simple', '2026-03-31', 'Sensitive skin formulas.'),
('brand', '$3 off Nivea body care', 'Nivea', '2026-03-31', NULL),
('brand', '$8 off Vichy skincare', 'Vichy', '2026-03-31', NULL),
('brand', '$5 off Yes To face masks', 'Yes To', '2026-02-28', NULL),
('brand', '$2 off St. Ives scrubs', 'St. Ives', '2026-03-31', NULL);

-- Hair Care Brands (12 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('brand', '$3 off Pantene shampoo or conditioner', 'Pantene', '2026-03-31', NULL),
('brand', 'Save $2 on any Herbal Essences product', 'Herbal Essences', '2026-03-31', NULL),
('brand', '$4 off TRESemmé hair care', 'TRESemmé', '2026-03-31', NULL),
('brand', 'Buy 2 Get 1 free on Garnier Fructis', 'Garnier Fructis', '2026-02-28', NULL),
('brand', '$2 off Dove hair care', 'Dove', '2026-03-31', NULL),
('brand', '$5 off OGX premium hair care', 'OGX', '2026-03-31', NULL),
('brand', '$3 off Aussie hair products', 'Aussie', '2026-03-31', NULL),
('brand', '$6 off It''s a 10 hair products', 'It''s a 10', '2026-03-31', NULL),
('brand', '$4 off L''Oreal hair color', 'L''Oreal', '2026-03-31', NULL),
('brand', '$3 off Clairol Nice ''n Easy', 'Clairol', '2026-03-31', NULL),
('brand', '$5 off John Frieda products', 'John Frieda', '2026-03-31', NULL),
('brand', '$2 off Suave hair care', 'Suave', '2026-03-31', NULL);

-- Cosmetics Brands (15 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('brand', '40% off all Maybelline cosmetics', 'Maybelline', '2026-03-31', NULL),
('brand', 'Buy 1 Get 1 50% off L''Oreal makeup', 'L''Oreal', '2026-02-28', NULL),
('brand', '$5 off $25 Revlon products', 'Revlon', '2026-03-31', NULL),
('brand', '$3 off CoverGirl cosmetics', 'CoverGirl', '2026-03-31', NULL),
('brand', '35% off NYX Professional Makeup', 'NYX', '2026-03-31', NULL),
('brand', '$10 off IT Cosmetics', 'IT Cosmetics', '2026-03-31', NULL),
('brand', '$4 off e.l.f. cosmetics', 'e.l.f.', '2026-03-31', NULL),
('brand', '30% off Wet n Wild makeup', 'Wet n Wild', '2026-03-31', NULL),
('brand', '$8 off Clinique makeup', 'Clinique', '2026-03-31', NULL),
('brand', '$15 off Estée Lauder cosmetics', 'Estée Lauder', '2026-03-31', NULL),
('brand', '$5 off Almay makeup', 'Almay', '2026-03-31', NULL),
('brand', '25% off Rimmel London', 'Rimmel', '2026-03-31', NULL),
('brand', '$3 off Essence cosmetics', 'Essence', '2026-03-31', NULL),
('brand', '$6 off Physicians Formula', 'Physicians Formula', '2026-03-31', NULL),
('brand', '$4 off Sally Hansen nail products', 'Sally Hansen', '2026-03-31', NULL);

-- Baby Brands (8 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('brand', '$3 off Pampers diapers', 'Pampers', '2026-03-31', 'Size 3 or larger.'),
('brand', 'Save $2 on Huggies wipes', 'Huggies', '2026-03-31', NULL),
('brand', '$4 off Similac formula', 'Similac', '2026-03-31', NULL),
('brand', '$4 off Enfamil formula', 'Enfamil', '2026-03-31', NULL),
('brand', '$2 off Johnson''s baby products', 'Johnson''s', '2026-03-31', NULL),
('brand', '$3 off Aveeno Baby products', 'Aveeno Baby', '2026-03-31', NULL),
('brand', '$2 off Huggies diapers', 'Huggies', '2026-03-31', NULL),
('brand', '$5 off Gerber baby food', 'Gerber', '2026-03-31', 'Purchase of 10 or more.');

-- Personal Care & Oral Care Brands (12 coupons)
INSERT INTO coupons (type, discount_details, category_or_brand, expiration_date, terms) VALUES
('brand', '$1.50 off Colgate toothpaste', 'Colgate', '2026-03-31', NULL),
('brand', '$5 off Philips Sonicare brush', 'Philips Sonicare', '2026-03-31', NULL),
('brand', '$1 off Crest toothpaste', 'Crest', '2026-03-31', NULL),
('brand', '$2 off Listerine mouthwash', 'Listerine', '2026-03-31', NULL),
('brand', '$1.50 off Sensodyne toothpaste', 'Sensodyne', '2026-03-31', 'For sensitive teeth.'),
('brand', '$2 off Dove deodorant', 'Dove', '2026-03-31', NULL),
('brand', '$1.50 off Degree deodorant', 'Degree', '2026-03-31', NULL),
('brand', '$2 off Secret deodorant', 'Secret', '2026-03-31', NULL),
('brand', '$3 off Gillette razors', 'Gillette', '2026-03-31', NULL),
('brand', '$2 off Schick razors', 'Schick', '2026-03-31', NULL),
('brand', '$1.50 off Irish Spring soap', 'Irish Spring', '2026-03-31', NULL),
('brand', '$2 off Dial body wash', 'Dial', '2026-03-31', NULL);

-- Verification query
SELECT 'Total coupons created:' as info, COUNT(*) as count FROM coupons
UNION ALL
SELECT 'Frontstore coupons:', COUNT(*) FROM coupons WHERE type = 'frontstore'
UNION ALL
SELECT 'Category coupons:', COUNT(*) FROM coupons WHERE type = 'category'
UNION ALL
SELECT 'Brand coupons:', COUNT(*) FROM coupons WHERE type = 'brand';
