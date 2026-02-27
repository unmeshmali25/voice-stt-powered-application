"""
Decision tracking system for LLM-based agent decisions.

Provides comprehensive audit trail logging to the database with:
- Full context, prompt, and response storage
- Cache hit/miss tracking
- Statistics aggregation
- A/B analysis support
- LangSmith tracing integration
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from langsmith import traceable

from app.supabase_client import supabase
from app.simulation.config import SimulationConfig

logger = logging.getLogger(__name__)


@dataclass
class DecisionRecord:
    """Record of a single LLM decision."""

    # Identification
    agent_id: str
    simulation_id: Optional[str] = None
    decision_type: str = ""  # "shop" or "checkout"

    # LLM metadata
    llm_tier: str = ""  # "fast" (Ollama) or "standard" (OpenRouter)
    llm_provider: str = ""  # "ollama" or "openrouter"
    llm_model: str = ""

    # Context and prompt
    context: Dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    response: str = ""

    # Decision output
    decision: bool = False
    confidence: float = 0.0
    reasoning: str = ""
    urgency: float = 0.0

    # Performance
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Cache status
    cache_hit: bool = False
    context_hash: str = ""

    # Timestamps
    simulated_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "agent_id": self.agent_id,
            "simulation_id": self.simulation_id,
            "decision_type": self.decision_type,
            "llm_tier": self.llm_tier,
            "llm_provider": self.llm_provider,
            "model_name": self.llm_model,
            "decision_context": self.context,
            "prompt_text": self.prompt,
            "raw_llm_response": self.response,
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "urgency": self.urgency,
            "latency_ms": self.latency_ms,
            "tokens_input": self.prompt_tokens,
            "tokens_output": self.completion_tokens,
            "cache_hit": self.cache_hit,
            "context_hash": self.context_hash,
            "simulated_timestamp": self.simulated_timestamp.isoformat()
            if self.simulated_timestamp
            else self.created_at.isoformat()
            if self.created_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DecisionTracker:
    """
    Tracks and logs LLM decisions with full audit trail.

    Features:
    - Database persistence with batching for performance
    - Cache effectiveness tracking
    - Statistics per agent and decision type
    - A/B analysis comparing LLM vs probability decisions
    - LangSmith tracing integration

    Usage:
        tracker = DecisionTracker()

        # Log an LLM decision
        await tracker.log_decision(
            agent_id="agent_001",
            decision_type="shop",
            llm_tier="fast",
            context={...},
            prompt="...",
            response="...",
            decision=True,
            confidence=0.85,
            latency_ms=450,
        )

        # Log a cache hit
        await tracker.log_cache_hit(agent_id, "shop", context_hash)

        # Flush to database
        await tracker.flush()
    """

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval_seconds: float = 10.0,
        simulation_id: Optional[str] = None,
    ):
        """
        Initialize the decision tracker.

        Args:
            batch_size: Number of decisions to queue before auto-flush
            flush_interval_seconds: Time between auto-flushes
            simulation_id: Optional simulation run identifier
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self.simulation_id = simulation_id

        # Queue for batching
        self._queue: List[DecisionRecord] = []
        self._queue_lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = (
            None  # Track which loop the lock belongs to
        )

        # Statistics
        self._stats = {
            "total_decisions": 0,
            "llm_decisions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "by_agent": defaultdict(
                lambda: {
                    "total": 0,
                    "llm": 0,
                    "cache_hits": 0,
                }
            ),
            "by_type": defaultdict(
                lambda: {
                    "total": 0,
                    "llm": 0,
                    "avg_confidence": 0.0,
                    "avg_latency_ms": 0.0,
                }
            ),
        }

        # Start auto-flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the auto-flush background task."""
        # Initialize lock in the correct event loop context
        self._queue_lock = asyncio.Lock()
        self._lock_loop = asyncio.get_running_loop()
        self._running = True
        self._flush_task = asyncio.create_task(self._auto_flush())
        logger.info("Decision tracker started")

    async def stop(self) -> None:
        """Stop the auto-flush task and flush remaining decisions."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush remaining queue
        await self.flush()
        logger.info("Decision tracker stopped")

    async def _auto_flush(self) -> None:
        """Background task to periodically flush the queue."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                if self._queue:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-flush: {e}")

    @traceable(run_type="llm")
    def _ensure_lock(self) -> None:
        """Ensure the queue lock is initialized in the current event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one
            current_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(current_loop)

        # Check if lock exists and belongs to current loop
        if self._queue_lock is None or self._lock_loop is not current_loop:
            self._queue_lock = asyncio.Lock()
            self._lock_loop = current_loop
            logger.debug(f"Created queue lock for event loop {id(current_loop)}")

    async def log_decision(
        self,
        agent_id: str,
        decision_type: str,
        llm_tier: str,
        llm_provider: str,
        llm_model: str,
        context: Dict[str, Any],
        prompt: str,
        response: str,
        decision: bool,
        confidence: float,
        reasoning: str,
        urgency: float = 0.0,
        latency_ms: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cache_hit: bool = False,
        context_hash: str = "",
        simulated_timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Log an LLM decision with full audit trail.

        Args:
            agent_id: Unique agent identifier
            decision_type: "shop" or "checkout"
            llm_tier: "fast" or "standard"
            llm_provider: "ollama" or "openrouter"
            llm_model: Model name used
            context: Full decision context dict
            prompt: Prompt sent to LLM
            response: Raw LLM response
            decision: Boolean decision outcome
            confidence: Confidence score (0-1)
            reasoning: Explanation from LLM
            urgency: Urgency score (0-1)
            latency_ms: Request latency in milliseconds
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            cache_hit: Whether result was from cache
            context_hash: Hash of context for cache tracking
            simulated_timestamp: Simulated timestamp for the decision
        """
        record = DecisionRecord(
            agent_id=agent_id,
            simulation_id=self.simulation_id,
            decision_type=decision_type,
            llm_tier=llm_tier,
            llm_provider=llm_provider,
            llm_model=llm_model,
            context=context,
            prompt=prompt,
            response=response,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            urgency=urgency,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_hit=cache_hit,
            context_hash=context_hash,
            simulated_timestamp=simulated_timestamp,
        )

        self._ensure_lock()
        async with self._queue_lock:
            self._queue.append(record)
            self._update_stats(record)

            # Auto-flush if queue is full
            if len(self._queue) >= self.batch_size:
                await self._flush_unlocked()

    async def log_cache_hit(
        self,
        agent_id: str,
        decision_type: str,
        context_hash: str,
    ) -> None:
        """
        Log a cache hit (no LLM call made).

        Args:
            agent_id: Agent identifier
            decision_type: Type of decision
            context_hash: Hash of the cached context
        """
        self._ensure_lock()
        async with self._queue_lock:
            self._stats["cache_hits"] += 1
            self._stats["by_agent"][agent_id]["cache_hits"] += 1

    async def log_cache_miss(self) -> None:
        """Log a cache miss (LLM call required)."""
        self._ensure_lock()
        async with self._queue_lock:
            self._stats["cache_misses"] += 1

    def _update_stats(self, record: DecisionRecord) -> None:
        """Update in-memory statistics."""
        self._stats["total_decisions"] += 1

        if not record.cache_hit:
            self._stats["llm_decisions"] += 1

        # Per-agent stats
        agent_stats = self._stats["by_agent"][record.agent_id]
        agent_stats["total"] += 1
        if not record.cache_hit:
            agent_stats["llm"] += 1

        # Per-type stats
        type_stats = self._stats["by_type"][record.decision_type]
        type_stats["total"] += 1
        if not record.cache_hit:
            type_stats["llm"] += 1
            # Update running averages
            n = type_stats["llm"]
            type_stats["avg_confidence"] = (
                type_stats["avg_confidence"] * (n - 1) + record.confidence
            ) / n
            type_stats["avg_latency_ms"] = (
                type_stats["avg_latency_ms"] * (n - 1) + record.latency_ms
            ) / n

    async def flush(self) -> int:
        """
        Flush queued decisions to the database.

        Returns:
            Number of records flushed
        """
        self._ensure_lock()
        async with self._queue_lock:
            return await self._flush_unlocked()

    async def _flush_unlocked(self) -> int:
        """
        Flush queue to database (must hold queue_lock).

        Returns:
            Number of records flushed
        """
        if not self._queue:
            return 0

        if not supabase:
            logger.warning("Supabase not configured, skipping database write")
            self._queue = []
            return 0

        records_to_flush = self._queue
        self._queue = []

        try:
            # Convert to dicts for insertion
            records_data = [r.to_dict() for r in records_to_flush]

            # Insert in batches to avoid request size limits
            batch_size = 50
            for i in range(0, len(records_data), batch_size):
                batch = records_data[i : i + batch_size]
                result = supabase.table("llm_decisions").insert(batch).execute()

                if hasattr(result, "error") and result.error:
                    logger.error(f"Error inserting decisions: {result.error}")
                else:
                    logger.debug(f"Flushed {len(batch)} decisions to database")

            logger.info(f"Successfully flushed {len(records_to_flush)} decisions")
            return len(records_to_flush)

        except Exception as e:
            logger.error(f"Failed to flush decisions: {e}")
            # Put records back in queue for retry
            self._queue = records_to_flush + self._queue
            return 0

    def get_decision_stats(
        self,
        agent_id: Optional[str] = None,
        decision_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics for decisions.

        Args:
            agent_id: Filter by specific agent (optional)
            decision_type: Filter by decision type (optional)

        Returns:
            Statistics dict
        """
        if agent_id:
            return dict(self._stats["by_agent"][agent_id])

        if decision_type:
            return dict(self._stats["by_type"][decision_type])

        # Overall stats
        total = self._stats["total_decisions"]
        cache_hits = self._stats["cache_hits"]
        cache_misses = self._stats["cache_misses"]
        cache_total = cache_hits + cache_misses

        return {
            "total_decisions": total,
            "llm_calls": self._stats["llm_decisions"],
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": cache_hits / cache_total if cache_total > 0 else 0.0,
            "by_type": dict(self._stats["by_type"]),
        }

    async def compare_to_probability(
        self,
        agent_ids: List[str],
        decision_type: str,
    ) -> Dict[str, Any]:
        """
        Compare LLM decisions to what probability would have decided.

        This is an A/B analysis helper that compares the actual decisions
        made by LLM with what would have happened under probability-based logic.

        Args:
            agent_ids: List of agent IDs to analyze
            decision_type: Type of decision ("shop" or "checkout")

        Returns:
            Comparison statistics
        """
        if not supabase:
            return {"error": "Supabase not configured"}

        try:
            # Query database for LLM decisions
            result = (
                supabase.table("llm_decisions")
                .select("*")
                .in_("agent_id", agent_ids)
                .eq("decision_type", decision_type)
                .execute()
            )

            if hasattr(result, "error") and result.error:
                return {"error": str(result.error)}

            decisions = result.data

            # Calculate statistics
            total = len(decisions)
            positive_decisions = sum(1 for d in decisions if d["decision"])
            avg_confidence = (
                sum(d["confidence"] for d in decisions) / total if total > 0 else 0
            )
            avg_latency = (
                sum(d["latency_ms"] for d in decisions) / total if total > 0 else 0
            )

            return {
                "total_decisions": total,
                "positive_rate": positive_decisions / total if total > 0 else 0,
                "avg_confidence": avg_confidence,
                "avg_latency_ms": avg_latency,
                "by_urgency": self._group_by_urgency(decisions),
            }

        except Exception as e:
            logger.error(f"Error comparing to probability: {e}")
            return {"error": str(e)}

    def _group_by_urgency(self, decisions: List[Dict]) -> Dict[str, int]:
        """Group decisions by urgency level."""
        groups = {"low": 0, "medium": 0, "high": 0}

        for d in decisions:
            urgency = d.get("urgency", 0)
            if urgency < 0.33:
                groups["low"] += 1
            elif urgency < 0.67:
                groups["medium"] += 1
            else:
                groups["high"] += 1

        return groups


# Global decision tracker instance
decision_tracker: Optional[DecisionTracker] = None


def get_decision_tracker(
    simulation_id: Optional[str] = None,
    batch_size: int = 100,
) -> DecisionTracker:
    """
    Get or create the global decision tracker instance.

    Args:
        simulation_id: Optional simulation run identifier
        batch_size: Batch size for database writes

    Returns:
        The global DecisionTracker instance
    """
    global decision_tracker
    if decision_tracker is None:
        decision_tracker = DecisionTracker(
            simulation_id=simulation_id,
            batch_size=batch_size,
        )
    return decision_tracker


def reset_decision_tracker() -> None:
    """Reset the global decision tracker."""
    global decision_tracker
    decision_tracker = None
