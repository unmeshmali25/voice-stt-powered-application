-- ============================================================================
-- Migration 008: Add Simulation Columns to Orders Table
-- Purpose: Support simulation tracking and enhanced analytics
-- Date: 2025-12-27
-- ============================================================================

-- Add item_count column for denormalized analytics
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS item_count INTEGER NOT NULL DEFAULT 0;

-- Add is_simulated column to distinguish simulation from real orders
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT false;

-- Create index on is_simulated for filtering
CREATE INDEX IF NOT EXISTS idx_orders_is_simulated ON orders(is_simulated);

-- Create index on item_count for analytics queries
CREATE INDEX IF NOT EXISTS idx_orders_item_count ON orders(item_count);

-- Add comment for documentation
COMMENT ON COLUMN orders.item_count IS 'Number of items in the order (denormalized for analytics)';
COMMENT ON COLUMN orders.is_simulated IS 'True if this order was created by simulation, false for real user orders';
