"""
Test suite for Sprint 2 LLM Infrastructure.

Tests Ollama integration, metrics collection, and decision engine
with qwen3:4b model.

Run with: pytest tests/test_sprint2_llm.py -v
"""

import asyncio
import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch, AsyncMock

from app.simulation.agent.state import AgentState
from app.simulation.agent.cache import DecisionCache
from app.simulation.agent.llm_decisions import LLMDecisionEngine, DecisionResult
from app.simulation.agent.decision_tracker import DecisionTracker
from app.simulation.metrics.llm_metrics import LLMMetricsCollector, get_metrics_collector
from app.simulation.generators.llm_client import LLMClient
from app.simulation.prompts.shopping_decisions import (
    SHOP_DECISION_PROMPT,
    CHECKOUT_DECISION_PROMPT,
    format_decision_prompt,
)
from app.simulation.config import SimulationConfig


class TestLLMMetricsCollector:
    """Test LLM metrics collection."""
    
    @pytest.fixture
    def collector(self):
        return LLMMetricsCollector()
    
    @pytest.mark.asyncio
    async def test_concurrent_call_tracking(self, collector):
        """Test tracking of concurrent calls."""
        await collector.start_call("ollama")
        await collector.start_call("ollama")
        
        summary = collector.get_provider_summary("ollama")
        assert summary["current_concurrent"] == 2
        assert summary["max_concurrent"] == 2
        
        await collector.end_call("ollama", latency=0.5, success=True)
        assert collector.get_provider_summary("ollama")["current_concurrent"] == 1
    
    @pytest.mark.asyncio
    async def test_latency_tracking(self, collector):
        """Test latency statistics."""
        # Simulate multiple calls
        for i in range(5):
            await collector.start_call("ollama")
            await collector.end_call("ollama", latency=0.1 * (i + 1), success=True)
        
        summary = collector.get_provider_summary("ollama")
        assert summary["latency"]["count"] == 5
        assert summary["latency"]["min"] > 0
        assert summary["latency"]["max"] > summary["latency"]["min"]
    
    @pytest.mark.asyncio
    async def test_error_tracking(self, collector):
        """Test error tracking."""
        await collector.start_call("ollama")
        await collector.end_call("ollama", latency=0.5, success=False, error_type="timeout")
        
        await collector.start_call("ollama")
        await collector.end_call("ollama", latency=0.3, success=False, error_type="timeout")
        
        summary = collector.get_provider_summary("ollama")
        assert summary["error_count"] == 2
        assert summary["errors_by_type"]["timeout"] == 2
        assert summary["error_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_cache_metrics(self, collector):
        """Test cache hit/miss tracking."""
        await collector.record_cache_hit()
        await collector.record_cache_hit()
        await collector.record_cache_miss()
        
        cache_summary = collector.get_cache_summary()
        assert cache_summary["hits"] == 2
        assert cache_summary["misses"] == 1
        assert cache_summary["hit_rate"] == 2/3
    
    @pytest.mark.asyncio
    async def test_decision_distribution(self, collector):
        """Test LLM vs probability decision tracking."""
        await collector.record_llm_decision()
        await collector.record_llm_decision()
        await collector.record_probability_decision()
        
        decision_summary = collector.get_decision_summary()
        assert decision_summary["llm_decisions"] == 2
        assert decision_summary["probability_decisions"] == 1
        assert decision_summary["llm_percentage"] == 2/3
    
    def test_realtime_summary(self, collector):
        """Test comprehensive realtime summary."""
        summary = collector.get_realtime_summary()
        
        assert "timestamp" in summary
        assert "uptime_seconds" in summary
        assert "providers" in summary
        assert "ollama" in summary["providers"]
        assert "openrouter" in summary["providers"]
        assert "cache" in summary
        assert "decisions" in summary


class TestDecisionTracker:
    """Test decision audit logging."""
    
    @pytest.fixture
    def tracker(self):
        return DecisionTracker(batch_size=10, simulation_id="test_sim")
    
    @pytest.mark.asyncio
    async def test_log_decision(self, tracker):
        """Test logging a single decision."""
        await tracker.log_decision(
            agent_id="agent_001",
            decision_type="shop",
            llm_tier="fast",
            llm_provider="ollama",
            llm_model="qwen3:4b",
            context={"test": "data"},
            prompt="test prompt",
            response='{"decision": true}',
            decision=True,
            confidence=0.85,
            reasoning="test reasoning",
            latency_ms=450,
        )
        
        stats = tracker.get_decision_stats()
        assert stats["total_decisions"] == 1
        assert stats["llm_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_cache_hit_tracking(self, tracker):
        """Test cache hit tracking."""
        await tracker.log_cache_hit("agent_001", "shop", "hash123")
        await tracker.log_cache_hit("agent_001", "shop", "hash456")
        
        stats = tracker.get_decision_stats(agent_id="agent_001")
        assert stats["cache_hits"] == 2
    
    @pytest.mark.asyncio
    async def test_queue_batching(self, tracker):
        """Test that decisions are queued and batched."""
        # Log decisions without flushing
        for i in range(5):
            await tracker.log_decision(
                agent_id=f"agent_{i:03d}",
                decision_type="shop",
                llm_tier="fast",
                llm_provider="ollama",
                llm_model="qwen3:4b",
                context={},
                prompt="test",
                response='{"decision": true}',
                decision=True,
                confidence=0.8,
                reasoning="test",
                latency_ms=100,
            )
        
        # Should be queued, not flushed yet
        assert len(tracker._queue) == 5


class TestOllamaClient:
    """Test Ollama client integration."""
    
    @pytest.fixture
    def config(self):
        return SimulationConfig()
    
    @pytest.fixture
    def client(self, config):
        return LLMClient(config)
    
    @pytest.mark.asyncio
    async def test_ollama_complete_mock(self, client):
        """Test Ollama completion with mocked response."""
        mock_response = {
            "response": '{"decision": true, "confidence": 0.85}'
        }
        
        with patch.object(
            client._get_ollama_session(),
            'post',
            return_value=AsyncMock(
                status=200,
                json=AsyncMock(return_value=mock_response)
            )
        ):
            response_text, usage_info = await client._ollama_complete(
                model="qwen3:4b",
                prompt="Test prompt",
                max_tokens=100,
                temperature=0.1,
            )
            
            assert "decision" in response_text
            assert usage_info["cost_usd"] == 0.0
            assert usage_info["time_seconds"] > 0
    
    def test_ollama_config_defaults(self, client):
        """Test Ollama configuration defaults."""
        config = client.OLLAMA_CONFIG
        assert config["temperature"] == 0.1
        assert config["max_tokens"] == 200
        assert config["timeout"] == 30
        assert config["batch_size"] == 8


class TestPromptTemplates:
    """Test prompt templates and formatting."""
    
    def test_shop_prompt_formatting(self):
        """Test shop decision prompt formatting."""
        context = {
            "persona_name": "Test Agent",
            "shopping_frequency": "regular",
            "impulsivity": 0.5,
            "budget_sensitivity": 0.6,
            "coupon_affinity": 0.7,
            "preferred_categories": "snacks, beverages",
            "pref_days": "Saturday, Sunday",
            "weekly_budget": 100,
            "avg_cart_value": 50,
            "current_date": "2024-11-28",
            "current_day_of_week": "Thursday",
            "active_events": "Black Friday",
            "days_since_last_shop": 5,
            "recent_orders": "3 recent orders, avg value $45.50",
            "monthly_spend": 180,
        }
        
        prompt = SHOP_DECISION_PROMPT.format(**context)
        
        assert "Test Agent" in prompt
        assert "Black Friday" in prompt
        assert "regular" in prompt
        assert "JSON" in prompt
    
    def test_checkout_prompt_formatting(self):
        """Test checkout decision prompt formatting."""
        context = {
            "persona_name": "Test Agent",
            "impulsivity": 0.5,
            "budget_sensitivity": 0.6,
            "brand_loyalty": 0.7,
            "cart_items": "4 items, total $78.50",
            "cart_total": "$78.50",
            "items_viewed": 12,
            "coupons_available": "2 available",
            "weekly_budget": "$100.00",
            "monthly_spend": "$180.00",
            "budget_status": "within budget",
        }
        
        prompt = CHECKOUT_DECISION_PROMPT.format(**context)
        
        assert "$78.50" in prompt
        assert "within budget" in prompt
        assert "JSON" in prompt
    
    def test_prompt_json_schema(self):
        """Test that prompts include valid JSON schema."""
        assert '"decision": true/false' in SHOP_DECISION_PROMPT
        assert '"confidence": 0.0-1.0' in SHOP_DECISION_PROMPT
        assert '"decision": true/false' in CHECKOUT_DECISION_PROMPT


class TestLLMDecisionEngine:
    """Test LLM decision engine."""
    
    @pytest.fixture
    def engine(self):
        config = SimulationConfig()
        return LLMDecisionEngine(config)
    
    @pytest.fixture
    def sample_agent_state(self):
        """Create a sample agent state for testing."""
        return AgentState(
            agent_id="test_agent_001",
            user_id="user_001",
            shopping_frequency="regular",
            impulsivity=0.5,
            price_sensitivity=0.6,
            coupon_affinity=0.7,
            preferred_categories=["snacks", "beverages", "household"],
            pref_day_weekday=0.3,
            pref_day_saturday=0.8,
            pref_day_sunday=0.6,
            weekly_budget=100.0,
            avg_cart_value=50.0,
            simulated_date=date(2024, 11, 28),
            cart_items=[],
            cart_total=0.0,
            products_viewed=[],
            recent_orders=[
                {"total": 45.50, "date": "2024-11-25"},
                {"total": 32.00, "date": "2024-11-20"},
            ],
            monthly_spend=180.0,
            last_shop_date=date(2024, 11, 25),
        )
    
    def test_build_shop_context(self, engine, sample_agent_state):
        """Test context building for shop decisions."""
        context = engine._build_shop_context(sample_agent_state)
        
        assert "shopping_frequency" in context
        assert context["shopping_frequency"] == "regular"
        assert "active_events" in context
        assert "recent_orders" in context
        assert context["days_since_last_shop"] == 3  # Nov 28 - Nov 25
    
    def test_build_checkout_context(self, engine):
        """Test context building for checkout decisions."""
        state = AgentState(
            agent_id="test_agent",
            cart_items=[
                {"product_id": "p1", "quantity": 2, "price": 10.0},
                {"product_id": "p2", "quantity": 1, "price": 25.0},
            ],
            cart_total=45.0,
            products_viewed=["p1", "p2", "p3", "p4"],
            coupons_available=[{"id": "c1", "type": "percent", "discount": "10%"}],
            weekly_budget=100.0,
            monthly_spend=180.0,
            impulsivity=0.5,
            price_sensitivity=0.6,
            brand_loyalty=0.7,
        )
        
        context = engine._build_checkout_context(state)
        
        assert "4 items" in context["cart_items"]
        assert "$45.00" == context["cart_total"]
        assert context["items_viewed"] == 4
    
    def test_parse_valid_response(self, engine):
        """Test parsing valid LLM response."""
        response_text = '''
        {
            "decision": true,
            "confidence": 0.85,
            "reasoning": "Good day to shop based on preferences",
            "urgency": 0.6
        }
        '''
        
        parsed = engine._parse_response(response_text)
        
        assert parsed["decision"] is True
        assert parsed["confidence"] == 0.85
        assert "Good day" in parsed["reasoning"]
        assert parsed["urgency"] == 0.6
    
    def test_parse_invalid_response(self, engine):
        """Test parsing invalid LLM response."""
        response_text = "Not valid JSON"
        
        parsed = engine._parse_response(response_text)
        
        assert parsed["decision"] is False
        assert parsed["confidence"] == 0.0
        assert "Parse error" in parsed["reasoning"]
    
    @pytest.mark.asyncio
    async def test_fallback_to_probability_shop(self, engine, sample_agent_state):
        """Test fallback to probability-based decision for shop."""
        result = await engine._fallback_to_probability(
            state=sample_agent_state,
            decision_type="shop",
            provider="ollama",
            latency_ms=500,
            error="Connection timeout",
        )
        
        assert isinstance(result, DecisionResult)
        assert result.llm_provider == "ollama_fallback"
        assert "FALLBACK" in result.reasoning
        assert result.error == "Connection timeout"
    
    @pytest.mark.asyncio
    async def test_fallback_to_probability_checkout(self, engine):
        """Test fallback to probability-based decision for checkout."""
        state = AgentState(
            agent_id="test_agent",
            impulsivity=0.8,  # High impulsivity
            price_sensitivity=0.3,  # Low price sensitivity
            cart_total=75.0,
            weekly_budget=100.0,
            monthly_spend=50.0,
            cart_items=[{"product_id": "p1", "quantity": 1, "price": 75.0}],
        )
        
        result = await engine._fallback_to_probability(
            state=state,
            decision_type="checkout",
            provider="ollama",
            latency_ms=300,
            error="Model error",
        )
        
        assert isinstance(result, DecisionResult)
        # High impulsivity should generally lead to completion
        # But this is probabilistic, so just check structure


class TestIntegration:
    """Integration tests for Sprint 2 components."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_decision_flow(self):
        """Test complete decision flow with mocked LLM."""
        # Setup
        config = SimulationConfig()
        engine = LLMDecisionEngine(config)
        
        state = AgentState(
            agent_id="integration_test",
            shopping_frequency="regular",
            impulsivity=0.5,
            price_sensitivity=0.5,
            simulated_date=date(2024, 11, 28),
            recent_orders=[],
            monthly_spend=0,
            cart_items=[{"product_id": "p1", "quantity": 1, "price": 25.0}],
            cart_total=25.0,
            products_viewed=["p1", "p2"],
            weekly_budget=100.0,
            monthly_spend=50.0,
        )
        
        # Mock the LLM call
        mock_response = '{"decision": true, "confidence": 0.8, "reasoning": "Test", "urgency": 0.5}'
        
        with patch.object(
            engine.llm_client,
            '_ollama_complete',
            return_value=(mock_response, {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "time_seconds": 0.5,
            })
        ):
            # Test shop decision
            result = await engine.decide_shop(state, tier="fast")
            
            assert isinstance(result, DecisionResult)
            assert result.decision is True
            assert result.confidence == 0.8
            assert result.cache_hit is False
            
            # Second call should hit cache
            result2 = await engine.decide_shop(state, tier="fast")
            assert result2.cache_hit is True
    
    def test_metrics_integration(self):
        """Test that metrics collector is shared globally."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        
        assert collector1 is collector2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
