-- ============================================================================
-- Migration 011: Add LLM Decisions Table
-- Creates comprehensive audit table for tracking all LLM-based decisions
-- with full context, prompts, responses, and performance metrics
-- ============================================================================

-- Create llm_decisions table for comprehensive decision tracking
CREATE TABLE IF NOT EXISTS llm_decisions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(agent_id),
    decision_type VARCHAR(20) NOT NULL,
    llm_tier VARCHAR(20) NOT NULL,
    simulated_timestamp TIMESTAMP NOT NULL,
    context_hash VARCHAR(64) NOT NULL,
    decision_context JSONB NOT NULL,
    prompt_text TEXT NOT NULL,
    raw_llm_response TEXT NOT NULL,
    decision BOOLEAN NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    reasoning TEXT,
    urgency VARCHAR(20),
    cache_hit BOOLEAN DEFAULT FALSE,
    latency_ms INTEGER,  -- Response time in milliseconds
    tokens_input INTEGER,
    tokens_output INTEGER,
    model_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_decision_type CHECK (decision_type IN ('shop', 'checkout')),
    CONSTRAINT valid_tier CHECK (llm_tier IN ('standard', 'fast'))
);

-- Add indexes for common query patterns
-- Index for agent lookups
CREATE INDEX IF NOT EXISTS idx_llm_decisions_agent 
ON llm_decisions(agent_id);

-- Index for decision type filtering
CREATE INDEX IF NOT EXISTS idx_llm_decisions_type 
ON llm_decisions(decision_type);

-- Index for temporal analysis
CREATE INDEX IF NOT EXISTS idx_llm_decisions_timestamp 
ON llm_decisions(simulated_timestamp);

-- Index for context-based cache lookups
CREATE INDEX IF NOT EXISTS idx_llm_decisions_context_hash 
ON llm_decisions(context_hash);

-- Index for tier-based analysis
CREATE INDEX IF NOT EXISTS idx_llm_decisions_tier 
ON llm_decisions(llm_tier);

-- Composite index for analytics queries
CREATE INDEX IF NOT EXISTS idx_llm_decisions_analytics 
ON llm_decisions(created_at, llm_tier, decision_type);

-- Index for cache effectiveness analysis
CREATE INDEX IF NOT EXISTS idx_llm_decisions_cache 
ON llm_decisions(cache_hit, context_hash) 
WHERE cache_hit = TRUE;

-- Add comments for documentation
COMMENT ON TABLE llm_decisions IS 'Audit log for all LLM-based agent decisions with full context';
COMMENT ON COLUMN llm_decisions.agent_id IS 'Foreign key to agents table';
COMMENT ON COLUMN llm_decisions.decision_type IS 'Type of decision: shop or checkout';
COMMENT ON COLUMN llm_decisions.llm_tier IS 'LLM tier used: standard (OpenRouter) or fast (Ollama)';
COMMENT ON COLUMN llm_decisions.context_hash IS 'SHA256 hash of normalized context for cache identification';
COMMENT ON COLUMN llm_decisions.decision_context IS 'Full JSON context including agent traits and temporal events';
COMMENT ON COLUMN llm_decisions.cache_hit IS 'Whether this decision was served from cache';
COMMENT ON COLUMN llm_decisions.latency_ms IS 'Time taken to get LLM response in milliseconds';

-- Create view for cache effectiveness metrics
CREATE OR REPLACE VIEW v_llm_cache_metrics AS
SELECT 
    llm_tier,
    decision_type,
    COUNT(*) as total_decisions,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits,
    SUM(CASE WHEN NOT cache_hit THEN 1 ELSE 0 END) as cache_misses,
    ROUND(
        100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 
        2
    ) as cache_hit_rate_pct,
    AVG(latency_ms) FILTER (WHERE NOT cache_hit) as avg_latency_ms_no_cache,
    AVG(latency_ms) FILTER (WHERE cache_hit) as avg_latency_ms_cache
FROM llm_decisions
GROUP BY llm_tier, decision_type;

-- Create view for decision quality analysis
CREATE OR REPLACE VIEW v_llm_decision_summary AS
SELECT 
    date_trunc('hour', created_at) as hour,
    llm_tier,
    decision_type,
    COUNT(*) as total_decisions,
    SUM(CASE WHEN decision THEN 1 ELSE 0 END) as positive_decisions,
    SUM(CASE WHEN NOT decision THEN 1 ELSE 0 END) as negative_decisions,
    AVG(confidence) as avg_confidence,
    AVG(latency_ms) as avg_latency_ms,
    AVG(tokens_input) as avg_tokens_input,
    AVG(tokens_output) as avg_tokens_output
FROM llm_decisions
GROUP BY date_trunc('hour', created_at), llm_tier, decision_type
ORDER BY hour DESC;

-- Verify table was created
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'llm_decisions'
    ) INTO table_exists;

    IF table_exists THEN
        RAISE NOTICE '✓ llm_decisions table created successfully';
    ELSE
        RAISE EXCEPTION '✗ llm_decisions table was not created';
    END IF;
END $$;

-- Verify indexes were created
DO $$
DECLARE
    expected_indexes INTEGER := 7;
    actual_indexes INTEGER;
BEGIN
    SELECT COUNT(*) INTO actual_indexes
    FROM pg_indexes
    WHERE tablename = 'llm_decisions';

    IF actual_indexes >= expected_indexes THEN
        RAISE NOTICE '✓ % indexes created on llm_decisions', actual_indexes;
    ELSE
        RAISE NOTICE '✗ Only % out of % expected indexes created', actual_indexes, expected_indexes;
    END IF;
END $$;
