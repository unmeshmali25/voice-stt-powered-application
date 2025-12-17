-- ============================================================================
-- Migration 006: Shopping Sessions + Event Tracking
-- Tracks a single user "shopping session" across search -> cart -> checkout.
-- ============================================================================

-- Sessions table (one per shopping flow)
CREATE TABLE IF NOT EXISTS shopping_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id UUID REFERENCES stores(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'abandoned')),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_shopping_sessions_user_id ON shopping_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_shopping_sessions_store_id ON shopping_sessions(store_id);
CREATE INDEX IF NOT EXISTS idx_shopping_sessions_status ON shopping_sessions(status);
CREATE INDEX IF NOT EXISTS idx_shopping_sessions_last_seen_at ON shopping_sessions(last_seen_at DESC);

-- Event log (many per session)
CREATE TABLE IF NOT EXISTS shopping_session_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES shopping_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shopping_session_events_session_id ON shopping_session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_shopping_session_events_user_id ON shopping_session_events(user_id);
CREATE INDEX IF NOT EXISTS idx_shopping_session_events_event_type ON shopping_session_events(event_type);
CREATE INDEX IF NOT EXISTS idx_shopping_session_events_created_at ON shopping_session_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shopping_session_events_payload_gin ON shopping_session_events USING GIN (payload);

-- Link orders to the session that produced them
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS shopping_session_id UUID REFERENCES shopping_sessions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_orders_shopping_session_id ON orders(shopping_session_id);

-- Enable RLS (consistent with other retail tables). Backend DB role may bypass RLS.
ALTER TABLE shopping_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_session_events ENABLE ROW LEVEL SECURITY;

-- Policies: users can only access their own session data
CREATE POLICY shopping_sessions_select_policy ON shopping_sessions
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY shopping_sessions_insert_policy ON shopping_sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY shopping_sessions_update_policy ON shopping_sessions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY shopping_session_events_select_policy ON shopping_session_events
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY shopping_session_events_insert_policy ON shopping_session_events
    FOR INSERT WITH CHECK (auth.uid() = user_id);


