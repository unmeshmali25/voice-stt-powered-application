-- ============================================================================
-- Migration 003: Seed Stores and Inventory Data
-- Run after 002_retail_cart_schema.sql
-- ============================================================================

-- ============================================================================
-- D-13: SEED STORES (10 stores)
-- ============================================================================
INSERT INTO stores (name) VALUES
    ('UM-store-1'),
    ('UM-store-2'),
    ('UM-store-3'),
    ('UM-store-4'),
    ('UM-store-5'),
    ('UM-store-6'),
    ('UM-store-7'),
    ('UM-store-8'),
    ('UM-store-9'),
    ('UM-store-10')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- D-14: SEED INVENTORY (10 stores × all products = 720 rows, 20 units each)
-- This creates inventory records for every product in every store
-- ============================================================================
INSERT INTO store_inventory (store_id, product_id, quantity)
SELECT s.id, p.id, 20
FROM stores s
CROSS JOIN products p
ON CONFLICT (store_id, product_id) DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
SELECT 'Stores created:' as info, COUNT(*) as count FROM stores
UNION ALL
SELECT 'Total inventory records:', COUNT(*) FROM store_inventory
UNION ALL
SELECT 'Products per store:', COUNT(DISTINCT product_id) FROM store_inventory WHERE store_id = (SELECT id FROM stores LIMIT 1);
