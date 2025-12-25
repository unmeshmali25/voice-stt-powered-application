-- Migration: 007_offer_engine.sql
-- Purpose: Create tables for simulation-only offer engine
-- Date: 2025-12-25

-- ============================================
-- DB-1: Create offer_cycles table
-- ============================================
CREATE TABLE IF NOT EXISTS offer_cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cycle_number INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    simulated_start_date DATE,
    simulated_end_date DATE,
    is_simulation BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_offer_cycles_ends_at ON offer_cycles(ends_at);
CREATE INDEX IF NOT EXISTS idx_offer_cycles_simulation ON offer_cycles(is_simulation);
CREATE UNIQUE INDEX IF NOT EXISTS idx_offer_cycles_number_sim ON offer_cycles(cycle_number, is_simulation);

-- ============================================
-- DB-2: Create user_offer_cycles table
-- ============================================
CREATE TABLE IF NOT EXISTS user_offer_cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_cycle_id UUID REFERENCES offer_cycles(id) ON DELETE SET NULL,
    last_refresh_at TIMESTAMP,
    next_refresh_at TIMESTAMP,
    is_simulation BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_offer_cycles_next_refresh ON user_offer_cycles(next_refresh_at);
CREATE INDEX IF NOT EXISTS idx_user_offer_cycles_user ON user_offer_cycles(user_id);

-- ============================================
-- DB-3: Add columns to user_coupons
-- ============================================
ALTER TABLE user_coupons ADD COLUMN IF NOT EXISTS status VARCHAR(20)
    DEFAULT 'active';

-- Add check constraint if not exists (PostgreSQL doesn't have IF NOT EXISTS for constraints)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'user_coupons_status_check'
    ) THEN
        ALTER TABLE user_coupons ADD CONSTRAINT user_coupons_status_check
            CHECK (status IN ('active', 'expired', 'used', 'removed'));
    END IF;
END $$;

ALTER TABLE user_coupons ADD COLUMN IF NOT EXISTS offer_cycle_id UUID
    REFERENCES offer_cycles(id) ON DELETE SET NULL;

ALTER TABLE user_coupons ADD COLUMN IF NOT EXISTS is_simulation BOOLEAN
    DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_user_coupons_status ON user_coupons(status);
CREATE INDEX IF NOT EXISTS idx_user_coupons_cycle ON user_coupons(offer_cycle_id);
CREATE INDEX IF NOT EXISTS idx_user_coupons_simulation ON user_coupons(is_simulation);

-- Backfill existing records
UPDATE user_coupons SET status = 'active' WHERE status IS NULL;
UPDATE user_coupons SET status = 'expired' WHERE eligible_until <= NOW() AND status = 'active';

-- ============================================
-- DB-4: Create simulation_state table
-- ============================================
CREATE TABLE IF NOT EXISTS simulation_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    simulation_start_time TIMESTAMP,
    real_start_time TIMESTAMP,
    simulation_calendar_start DATE,
    current_simulated_date DATE,
    is_active BOOLEAN DEFAULT false,
    time_scale DECIMAL(10,2) DEFAULT 168.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT simulation_state_singleton CHECK (id = 1)
);

-- Insert default row
INSERT INTO simulation_state (id, is_active)
VALUES (1, false)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- DB-5: Create agents table (28 structured columns)
-- ============================================
CREATE TABLE IF NOT EXISTS agents (
    -- Primary Keys & Links
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Metadata
    generation_model VARCHAR(100),
    generated_at TIMESTAMP,

    -- Demographics (7 fields)
    age INTEGER CHECK (age >= 18 AND age <= 100),
    age_group VARCHAR(20),
    gender VARCHAR(30),
    income_bracket VARCHAR(20),
    household_size INTEGER CHECK (household_size >= 1 AND household_size <= 10),
    has_children BOOLEAN DEFAULT false,
    location_region VARCHAR(100),

    -- Behavioral Traits (4 fields, 0.0-1.0 scale)
    price_sensitivity DECIMAL(3,2) CHECK (price_sensitivity >= 0 AND price_sensitivity <= 1),
    brand_loyalty DECIMAL(3,2) CHECK (brand_loyalty >= 0 AND brand_loyalty <= 1),
    impulsivity DECIMAL(3,2) CHECK (impulsivity >= 0 AND impulsivity <= 1),
    tech_savviness DECIMAL(3,2) CHECK (tech_savviness >= 0 AND tech_savviness <= 1),

    -- Shopping Preferences (4 fields)
    preferred_categories TEXT,
    weekly_budget DECIMAL(10,2),
    shopping_frequency VARCHAR(20),
    avg_cart_value DECIMAL(10,2),

    -- Temporal Patterns - Days (3 fields, 0.0-1.0)
    pref_day_weekday DECIMAL(3,2),
    pref_day_saturday DECIMAL(3,2),
    pref_day_sunday DECIMAL(3,2),

    -- Temporal Patterns - Times (3 fields, 0.0-1.0)
    pref_time_morning DECIMAL(3,2),
    pref_time_afternoon DECIMAL(3,2),
    pref_time_evening DECIMAL(3,2),

    -- Coupon Behavior (2 fields)
    coupon_affinity DECIMAL(3,2) CHECK (coupon_affinity >= 0 AND coupon_affinity <= 1),
    deal_seeking_behavior VARCHAR(30),

    -- Narrative Text (2 fields)
    backstory TEXT,
    sample_shopping_patterns TEXT,

    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_user_id ON agents(user_id);
CREATE INDEX IF NOT EXISTS idx_agents_coupon_affinity ON agents(coupon_affinity);
CREATE INDEX IF NOT EXISTS idx_agents_price_sensitivity ON agents(price_sensitivity);
CREATE INDEX IF NOT EXISTS idx_agents_income_bracket ON agents(income_bracket);
CREATE INDEX IF NOT EXISTS idx_agents_age_group ON agents(age_group);
