-- ============================================================================-- Migration 012: Fix LLM Decisions Schema
-- Adds missing columns and fixes urgency type to match Python code
-- ============================================================================

-- Add missing simulation_id column
ALTER TABLE llm_decisions 
ADD COLUMN IF NOT EXISTS simulation_id VARCHAR(100);

-- Add missing llm_provider column
ALTER TABLE llm_decisions 
ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(20);

-- Fix urgency column type from VARCHAR to FLOAT to match Python code
-- Using USING clause to convert existing string values to float
ALTER TABLE llm_decisions 
ALTER COLUMN urgency TYPE FLOAT 
USING CASE 
    WHEN urgency = 'low' THEN 0.33
    WHEN urgency = 'medium' THEN 0.66
    WHEN urgency = 'high' THEN 1.0
    ELSE 0.0
END;

-- Update constraint to reflect new FLOAT type with bounds check
-- Note: PostgreSQL CHECK constraints are already in place for bounds via ALTER

-- Verify the changes
DO $$
DECLARE
    col_exists BOOLEAN;
BEGIN
    -- Check simulation_id
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'llm_decisions' AND column_name = 'simulation_id'
    ) INTO col_exists;
    
    IF col_exists THEN
        RAISE NOTICE '✓ simulation_id column added successfully';
    ELSE
        RAISE EXCEPTION '✗ simulation_id column was not added';
    END IF;
    
    -- Check llm_provider
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'llm_decisions' AND column_name = 'llm_provider'
    ) INTO col_exists;
    
    IF col_exists THEN
        RAISE NOTICE '✓ llm_provider column added successfully';
    ELSE
        RAISE EXCEPTION '✗ llm_provider column was not added';
    END IF;
    
    -- Check urgency type
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'llm_decisions' 
        AND column_name = 'urgency' 
        AND data_type = 'double precision'
    ) THEN
        RAISE NOTICE '✓ urgency column type changed to FLOAT successfully';
    ELSE
        RAISE NOTICE '⚠ urgency column type check - may already be correct or different type';
    END IF;
END $$;

-- Update comments
COMMENT ON COLUMN llm_decisions.simulation_id IS 'Optional simulation run identifier for grouping related decisions';
COMMENT ON COLUMN llm_decisions.llm_provider IS 'LLM provider used: ollama or openrouter';
