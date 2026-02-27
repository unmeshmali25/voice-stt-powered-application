"""
LLM Decision Engine for agent shopping decisions.

Provides intelligent decision-making using LLM reasoning with:
- Rich context building from AgentState
- Structured JSON responses with confidence scores
- Cache integration for performance
- Fallback to probability-based decisions on failure
- Support for both fast (Ollama) and standard (OpenRouter) tiers
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.simulation.agent.state import AgentState
from app.simulation.agent.cache import DecisionCache
from app.simulation.agent.decision_tracker import DecisionTracker, get_decision_tracker
from app.simulation.metrics.llm_metrics import (
    LLMMetricsCollector,
    get_metrics_collector,
)
from app.simulation.generators.llm_client import LLMClient
from app.simulation.config import SimulationConfig
from app.simulation.temporal.events import EventCalendar

logger = logging.getLogger(__name__)


@dataclass
class DecisionResult:
    """Result of an LLM decision."""

    decision: bool
    confidence: float
    reasoning: str
    urgency: float
    llm_provider: str
    latency_ms: int
    cache_hit: bool
    error: Optional[str] = None


class LLMDecisionEngine:
    """
    LLM-powered decision engine for agent shopping behavior.

    Makes intelligent decisions about:
    - Whether an agent should shop today (decide_shop)
    - Whether to complete or abandon checkout (decide_checkout)

    Features:
    - Rich context building from agent traits and history
    - Integration with temporal event calendar
    - Cache-first approach for performance
    - Comprehensive metrics and audit logging
    - Automatic fallback to probability on LLM failure

    Usage:
        engine = LLMDecisionEngine(config)

        # Shop decision
        result = await engine.decide_shop(agent_state, tier="fast")
        if result.decision:
            # Agent shops today

        # Checkout decision
        result = await engine.decide_checkout(agent_state, tier="fast")
        if result.decision:
            # Complete purchase
    """

    def __init__(
        self,
        config: SimulationConfig,
        cache: Optional[DecisionCache] = None,
        metrics: Optional[LLMMetricsCollector] = None,
        tracker: Optional[DecisionTracker] = None,
    ):
        """
        Initialize the LLM decision engine.

        Args:
            config: Simulation configuration
            cache: Optional decision cache (creates default if not provided)
            metrics: Optional metrics collector (uses global if not provided)
            tracker: Optional decision tracker (uses global if not provided)
        """
        self.config = config
        self.cache = cache or DecisionCache()
        self.metrics = metrics or get_metrics_collector()
        self.tracker = tracker or get_decision_tracker()
        self.llm_client = LLMClient(config)
        self.event_calendar = EventCalendar()

        # Provider mapping by tier
        self.tier_to_provider = {
            "fast": "ollama",
            "standard": "openrouter",
        }

        # Model mapping by tier
        self.tier_to_model = {
            "fast": "qwen3:4b",  # Local Ollama model
            "standard": config.model,  # From config (OpenRouter)
        }

    async def decide_shop(
        self,
        state: AgentState,
        tier: str = "fast",
    ) -> DecisionResult:
        """
        Decide if the agent should shop today.

        Args:
            state: Current agent state
            tier: "fast" (Ollama) or "standard" (OpenRouter)

        Returns:
            DecisionResult with decision and metadata
        """
        decision_type = "shop"

        # Build context for cache key
        context = self._build_shop_context(state)
        agent_id = state.get("agent_id", "unknown")

        # Check cache first
        cached_result = await self.cache.get(agent_id, decision_type, context)
        if cached_result is not None:
            await self.metrics.record_cache_hit()
            await self.tracker.log_cache_hit(agent_id, decision_type, "")
            return DecisionResult(
                decision=cached_result.get("decision", False),
                confidence=cached_result.get("confidence", 0.0),
                reasoning="[cached] " + cached_result.get("reasoning", ""),
                urgency=cached_result.get("urgency", 0.0),
                llm_provider="cache",
                latency_ms=0,
                cache_hit=True,
            )

        await self.metrics.record_cache_miss()

        # Get provider and model for this tier
        provider = self.tier_to_provider.get(tier, "ollama")
        model = self.tier_to_model.get(tier, "qwen3:4b")

        # Track concurrent call
        await self.metrics.start_call(provider)

        start_time = time.time()

        try:
            # Build prompt
            from app.simulation.prompts.shopping_decisions import SHOP_DECISION_PROMPT

            prompt = SHOP_DECISION_PROMPT.format(**context)

            # Call LLM
            if provider == "ollama":
                response_text, usage_info = await self.llm_client._ollama_complete(
                    model=model,
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.1,
                    system="You are a shopping behavior simulator. Respond only with valid JSON.",
                )
            else:
                response_text, usage_info = await self.llm_client.complete(
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.1,
                )

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse response
            parsed = self._parse_response(response_text)

            # Store in cache
            await self.cache.set(
                agent_id,
                decision_type,
                context,
                bool(parsed.get("decision", False)),
                confidence=parsed.get("confidence"),
                reasoning=parsed.get("reasoning"),
                urgency=parsed.get("urgency"),
            )

            # Track metrics
            await self.metrics.end_call(provider, latency_ms / 1000, success=True)
            await self.metrics.record_llm_decision()

            # Log decision
            await self.tracker.log_decision(
                agent_id=agent_id,
                decision_type=decision_type,
                llm_tier=tier,
                llm_provider=provider,
                llm_model=model,
                context=context,
                prompt=prompt,
                response=response_text,
                decision=parsed.get("decision", False),
                confidence=parsed.get("confidence", 0.0),
                reasoning=parsed.get("reasoning", ""),
                urgency=parsed.get("urgency", 0.0),
                latency_ms=latency_ms,
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                cache_hit=False,
            )

            return DecisionResult(
                decision=parsed.get("decision", False),
                confidence=parsed.get("confidence", 0.0),
                reasoning=parsed.get("reasoning", ""),
                urgency=parsed.get("urgency", 0.0),
                llm_provider=provider,
                latency_ms=latency_ms,
                cache_hit=False,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            await self.metrics.end_call(
                provider, latency_ms / 1000, success=False, error_type=type(e).__name__
            )
            logger.error(f"LLM decision failed for {agent_id}: {e}")

            # Fallback to probability-based decision
            return await self._fallback_to_probability(
                state, decision_type, provider, latency_ms, str(e)
            )

    async def decide_checkout(
        self,
        state: AgentState,
        tier: str = "fast",
    ) -> DecisionResult:
        """
        Decide whether to complete checkout or abandon cart.

        Args:
            state: Current agent state
            tier: "fast" (Ollama) or "standard" (OpenRouter)

        Returns:
            DecisionResult with decision and metadata
        """
        decision_type = "checkout"

        # Build context
        context = self._build_checkout_context(state)
        agent_id = state.get("agent_id", "unknown")

        # Check cache
        cached_result = await self.cache.get(agent_id, decision_type, context)
        if cached_result is not None:
            await self.metrics.record_cache_hit()
            await self.tracker.log_cache_hit(agent_id, decision_type, "")
            return DecisionResult(
                decision=cached_result.get("decision", False),
                confidence=cached_result.get("confidence", 0.0),
                reasoning="[cached] " + cached_result.get("reasoning", ""),
                urgency=cached_result.get("urgency", 0.0),
                llm_provider="cache",
                latency_ms=0,
                cache_hit=True,
            )

        await self.metrics.record_cache_miss()

        # Get provider and model
        provider = self.tier_to_provider.get(tier, "ollama")
        model = self.tier_to_model.get(tier, "qwen3:4b")

        # Track concurrent call
        await self.metrics.start_call(provider)

        start_time = time.time()

        try:
            # Build prompt
            from app.simulation.prompts.shopping_decisions import (
                CHECKOUT_DECISION_PROMPT,
            )

            prompt = CHECKOUT_DECISION_PROMPT.format(**context)

            # Call LLM
            if provider == "ollama":
                response_text, usage_info = await self.llm_client._ollama_complete(
                    model=model,
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.1,
                    system="You are a shopping behavior simulator. Respond only with valid JSON.",
                )
            else:
                response_text, usage_info = await self.llm_client.complete(
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.1,
                )

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse response
            parsed = self._parse_response(response_text)

            # Store in cache
            await self.cache.set(
                agent_id,
                decision_type,
                context,
                bool(parsed.get("decision", False)),
                confidence=parsed.get("confidence"),
                reasoning=parsed.get("reasoning"),
                urgency=parsed.get("urgency"),
            )

            # Track metrics
            await self.metrics.end_call(provider, latency_ms / 1000, success=True)
            await self.metrics.record_llm_decision()

            # Log decision
            await self.tracker.log_decision(
                agent_id=agent_id,
                decision_type=decision_type,
                llm_tier=tier,
                llm_provider=provider,
                llm_model=model,
                context=context,
                prompt=prompt,
                response=response_text,
                decision=parsed.get("decision", False),
                confidence=parsed.get("confidence", 0.0),
                reasoning=parsed.get("reasoning", ""),
                urgency=parsed.get("urgency", 0.0),
                latency_ms=latency_ms,
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                cache_hit=False,
            )

            return DecisionResult(
                decision=parsed.get("decision", False),
                confidence=parsed.get("confidence", 0.0),
                reasoning=parsed.get("reasoning", ""),
                urgency=parsed.get("urgency", 0.0),
                llm_provider=provider,
                latency_ms=latency_ms,
                cache_hit=False,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            await self.metrics.end_call(
                provider, latency_ms / 1000, success=False, error_type=type(e).__name__
            )
            logger.error(f"LLM checkout decision failed for {agent_id}: {e}")

            # Fallback to probability
            return await self._fallback_to_probability(
                state, decision_type, provider, latency_ms, str(e)
            )

    def _build_shop_context(self, state: AgentState) -> Dict[str, Any]:
        """
        Build rich context for shop decision.

        Args:
            state: Agent state

        Returns:
            Context dictionary for prompt formatting
        """
        current_date = state.get("simulated_date")

        # Get active events
        active_events = []
        if current_date:
            temporal_context = self.event_calendar.get_context_for_date(current_date)
            active_events = temporal_context.get("active_events", [])

        # Get recent orders summary
        recent_orders = state.get("recent_orders", [])
        order_summary = f"{len(recent_orders)} recent orders"
        if recent_orders:
            avg_order_value = sum(o.get("total", 0) for o in recent_orders) / len(
                recent_orders
            )
            order_summary += f", avg value ${avg_order_value:.2f}"

        # Calculate days since last shop
        days_since_last_shop = "N/A"
        last_shop = state.get("last_shop_date")
        if last_shop and current_date:
            days_since_last_shop = (current_date - last_shop).days

        # Preferred days formatting
        pref_days = []
        if state.get("pref_day_weekday", 0) > 0.5:
            pref_days.append("weekdays")
        if state.get("pref_day_saturday", 0) > 0.5:
            pref_days.append("Saturday")
        if state.get("pref_day_sunday", 0) > 0.5:
            pref_days.append("Sunday")

        return {
            "persona_name": f"Agent {state.get('agent_id', 'unknown')}",
            "shopping_frequency": state.get("shopping_frequency", "unknown"),
            "impulsivity": state.get("impulsivity", 0.5),
            "price_sensitivity": state.get("price_sensitivity", 0.5),
            "budget_sensitivity": state.get("price_sensitivity", 0.5),  # Alias
            "coupon_affinity": state.get("coupon_affinity", 0.5),
            "preferred_categories": ", ".join(
                state.get("preferred_categories", [])[:3]
            ),
            "pref_days": ", ".join(pref_days) if pref_days else "flexible",
            "weekly_budget": state.get("weekly_budget", 0),
            "current_date": str(current_date) if current_date else "unknown",
            "current_day_of_week": current_date.strftime("%A")
            if current_date
            else "unknown",
            "active_events": ", ".join(active_events) if active_events else "none",
            "recent_orders": order_summary,
            "monthly_spend": state.get("monthly_spend", 0),
            "days_since_last_shop": days_since_last_shop,
            "avg_cart_value": state.get("avg_cart_value", 50),
        }

    def _build_checkout_context(self, state: AgentState) -> Dict[str, Any]:
        """
        Build rich context for checkout decision.

        Args:
            state: Agent state

        Returns:
            Context dictionary for prompt formatting
        """
        cart_items = state.get("cart_items", [])
        cart_total = state.get("cart_total", 0)
        coupons_available = state.get("coupons_available", [])

        # Build cart summary
        item_count = len(cart_items)
        item_summary = f"{item_count} items, total ${cart_total:.2f}"

        # Check budget status
        weekly_budget = state.get("weekly_budget", 0)
        monthly_spend = state.get("monthly_spend", 0)
        budget_status = "within budget"
        if weekly_budget > 0 and cart_total > weekly_budget * 0.5:
            budget_status = "approaching weekly limit"
        if monthly_spend > 0 and monthly_spend > weekly_budget * 4 * 0.8:
            budget_status = "near monthly limit"

        # Coupon summary
        coupon_summary = f"{len(coupons_available)} available"

        return {
            "persona_name": f"Agent {state.get('agent_id', 'unknown')}",
            "impulsivity": state.get("impulsivity", 0.5),
            "price_sensitivity": state.get("price_sensitivity", 0.5),
            "budget_sensitivity": state.get("price_sensitivity", 0.5),
            "brand_loyalty": state.get("brand_loyalty", 0.5),
            "cart_items": item_summary,
            "cart_total": f"${cart_total:.2f}",
            "coupons_available": coupon_summary,
            "weekly_budget": f"${weekly_budget:.2f}",
            "monthly_spend": f"${monthly_spend:.2f}",
            "budget_status": budget_status,
            "items_viewed": len(state.get("products_viewed", [])),
        }

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse structured JSON response from LLM.

        Args:
            response_text: Raw LLM response

        Returns:
            Parsed dictionary with decision, confidence, reasoning, urgency
        """
        try:
            # Use LLMClient's JSON extraction
            parsed = LLMClient._extract_json(response_text)

            # Validate and set defaults
            return {
                "decision": bool(parsed.get("decision", False)),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reasoning": str(parsed.get("reasoning", "No reasoning provided")),
                "urgency": float(parsed.get("urgency", 0.0)),
            }
        except Exception as e:
            logger.warning(
                f"Failed to parse LLM response: {e}\nResponse: {response_text[:200]}"
            )
            # Return default values
            return {
                "decision": False,
                "confidence": 0.0,
                "reasoning": f"Parse error: {str(e)}",
                "urgency": 0.0,
            }

    async def _fallback_to_probability(
        self,
        state: AgentState,
        decision_type: str,
        provider: str,
        latency_ms: int,
        error: str,
    ) -> DecisionResult:
        """
        Fallback to probability-based decision when LLM fails.

        Args:
            state: Agent state
            decision_type: Type of decision
            provider: LLM provider that failed
            latency_ms: Time spent before failure
            error: Error message

        Returns:
            DecisionResult using probability logic
        """
        import random

        # Simple probability-based logic
        if decision_type == "shop":
            # Base probability on shopping frequency
            freq_map = {
                "frequent": 0.7,
                "regular": 0.4,
                "occasional": 0.2,
                "rare": 0.1,
            }
            base_prob = freq_map.get(state.get("shopping_frequency", "regular"), 0.4)

            # Adjust for day preference
            current_date = state.get("simulated_date")
            if current_date:
                day_name = current_date.strftime("%A").lower()
                if day_name in ["saturday", "sunday"]:
                    if (
                        state.get(
                            "pref_day_saturday"
                            if day_name == "saturday"
                            else "pref_day_sunday",
                            0,
                        )
                        > 0.5
                    ):
                        base_prob *= 1.3
                else:
                    if state.get("pref_day_weekday", 0) > 0.5:
                        base_prob *= 1.2

            decision = random.random() < min(base_prob, 0.9)

        else:  # checkout
            # Base on cart value vs budget
            cart_total = state.get("cart_total", 0)
            weekly_budget = state.get("weekly_budget", 1)

            if weekly_budget > 0:
                cart_ratio = cart_total / weekly_budget
                if cart_ratio > 0.8:
                    base_prob = 0.7  # High investment, likely to complete
                elif cart_ratio > 0.5:
                    base_prob = 0.5
                else:
                    base_prob = 0.3
            else:
                base_prob = 0.5

            # Adjust for impulsivity
            impulsivity = state.get("impulsivity", 0.5)
            base_prob = base_prob * (0.7 + impulsivity * 0.6)

            decision = random.random() < min(base_prob, 0.9)

        await self.metrics.record_probability_decision()

        return DecisionResult(
            decision=decision,
            confidence=0.5,
            reasoning=f"[FALLBACK - {provider} failed] Probability-based decision. Error: {error[:50]}",
            urgency=0.0,
            llm_provider=f"{provider}_fallback",
            latency_ms=latency_ms,
            cache_hit=False,
            error=error,
        )


# Global engine instance
_decision_engine: Optional[LLMDecisionEngine] = None


def get_decision_engine(
    config: Optional[SimulationConfig] = None,
) -> LLMDecisionEngine:
    """
    Get or create the global decision engine instance.

    Args:
        config: Optional simulation configuration

    Returns:
        The global LLMDecisionEngine instance
    """
    global _decision_engine
    if _decision_engine is None:
        if config is None:
            config = SimulationConfig()
        _decision_engine = LLMDecisionEngine(config)
    return _decision_engine


def reset_decision_engine() -> None:
    """Reset the global decision engine."""
    global _decision_engine
    _decision_engine = None
