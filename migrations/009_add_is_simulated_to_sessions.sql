-- ============================================================================
-- Migration 009: Add is_simulated to Shopping Sessions
-- Purpose: Distinguish simulation data from real user sessions
-- Date: 2025-01-04
-- ============================================================================

-- Add is_simulated column to shopping_sessions
ALTER TABLE shopping_sessions
    ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT false;

-- Add is_simulated column to shopping_session_events
ALTER TABLE shopping_session_events
    ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT false;

-- Create indexes for filtering
CREATE INDEX IF NOT EXISTS idx_shopping_sessions_is_simulated ON shopping_sessions(is_simulated);
CREATE INDEX IF NOT EXISTS idx_shopping_session_events_is_simulated ON shopping_session_events(is_simulated);

-- Add comments for documentation
COMMENT ON COLUMN shopping_sessions.is_simulated IS 'True if this session was created by simulation, false for real user sessions';
COMMENT ON COLUMN shopping_session_events.is_simulated IS 'True if this event was created by simulation, false for real user events';

-- Backfill: Mark existing agent sessions as simulated
-- (Sessions belonging to users that are linked to agents)
UPDATE shopping_sessions
SET is_simulated = true
WHERE user_id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL)
  AND is_simulated = false;

UPDATE shopping_session_events
SET is_simulated = true
WHERE user_id IN (SELECT user_id FROM agents WHERE user_id IS NOT NULL)
  AND is_simulated = false;
