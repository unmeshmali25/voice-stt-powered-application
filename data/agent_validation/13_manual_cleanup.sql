-- ============================================
-- MANUAL SIMULATION DATA CLEANUP
-- ============================================
--
-- ⚠️  SAFETY NOTICE: This script does NOT delete agents!
-- Agents are permanent and managed via scripts/seed_simulation_agents.py
--
-- What this deletes:
--   ✓ Simulated sessions, orders, events (is_simulated = true)
--   ✓ Cart items and coupons for agent users
--   ✓ User coupons/offer cycles (is_simulation = true)
--
-- WARNING: This will delete ALL simulation data!
-- Make sure you want to do this before running.

BEGIN;

-- 1. Delete shopping session events (simulated)
DELETE FROM shopping_session_events
WHERE is_simulated = true;

-- 2. Delete shopping sessions (simulated)
DELETE FROM shopping_sessions
WHERE is_simulated = true;

-- 3. Delete order items for simulated orders
DELETE FROM order_items
WHERE order_id IN (
    SELECT id FROM orders WHERE is_simulated = true
);

-- 4. Delete simulated orders
DELETE FROM orders
WHERE is_simulated = true;

-- 5. Delete cart items for agent users
DELETE FROM cart_items
WHERE user_id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL);

-- 6. Delete cart coupons for agent users
DELETE FROM cart_coupons
WHERE user_id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL);

-- 7. Delete coupon interactions for agent users
DELETE FROM coupon_interactions
WHERE user_id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL);

-- 8. Delete user preferences for agent users
DELETE FROM user_preferences
WHERE user_id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL);

-- 9. Delete simulation user coupons
DELETE FROM user_coupons WHERE is_simulation = true;

-- 10. Delete simulation user offer cycles
DELETE FROM user_offer_cycles WHERE is_simulation = true;

-- 11. Delete simulation offer cycles
DELETE FROM offer_cycles WHERE is_simulation = true;

-- ============================================
-- AGENT DELETION DISABLED FOR SAFETY
-- ============================================
-- Agents are permanent fixtures managed separately.
-- To rebuild agents, use: python scripts/seed_simulation_agents.py --force
--
-- DANGER: Uncommenting these lines will DELETE ALL AGENTS!
-- Only do this if you're rebuilding the entire database from scratch.
-- ============================================

-- 12. Delete agent users from users table (DISABLED)
-- DELETE FROM users
-- WHERE id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL);

-- 13. Delete agents (DISABLED)
-- DELETE FROM agents;

-- 14. Reset simulation state
UPDATE simulation_state
SET is_active = false,
    current_simulated_date = NULL,
    simulation_calendar_start = NULL,
    simulation_start_time = NULL,
    real_start_time = NULL,
    time_scale = 168.0,
    updated_at = NOW()
WHERE id = 1;

COMMIT;

-- Verify cleanup
SELECT 'agents' as table_name, COUNT(*) as remaining FROM agents
UNION ALL
SELECT 'shopping_sessions (simulated)', COUNT(*) FROM shopping_sessions WHERE is_simulated = true
UNION ALL
SELECT 'shopping_session_events (simulated)', COUNT(*) FROM shopping_session_events WHERE is_simulated = true
UNION ALL
SELECT 'orders (simulated)', COUNT(*) FROM orders WHERE is_simulated = true
UNION ALL
SELECT 'user_coupons (simulation)', COUNT(*) FROM user_coupons WHERE is_simulation = true
UNION ALL
SELECT 'offer_cycles (simulation)', COUNT(*) FROM offer_cycles WHERE is_simulation = true;
