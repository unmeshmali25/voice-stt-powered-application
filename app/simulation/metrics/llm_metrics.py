"""
Real-time LLM metrics collector for observability.

Tracks concurrent calls, latency, errors, cache performance, and decision distribution
across multiple LLM providers (Ollama and OpenRouter).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class ProviderMetrics:
    """Metrics for a single LLM provider."""

    # Concurrent tracking
    current_concurrent: int = 0
    max_concurrent: int = 0

    # Latency tracking (last 100 calls for moving average)
    latencies: deque = field(default_factory=lambda: deque(maxlen=100))

    # Error tracking
    total_calls: int = 0
    error_count: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=dict)

    # Queue depth (if applicable)
    queue_depth: int = 0
    max_queue_depth: int = 0


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups


@dataclass
class DecisionMetrics:
    """Decision distribution metrics."""

    llm_decisions: int = 0
    probability_decisions: int = 0

    @property
    def total_decisions(self) -> int:
        return self.llm_decisions + self.probability_decisions

    @property
    def llm_percentage(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.llm_decisions / self.total_decisions


class LLMMetricsCollector:
    """
    Thread-safe collector for LLM performance metrics.

    Tracks real-time metrics across multiple providers:
    - Ollama (local fast tier)
    - OpenRouter (standard tier)

    Usage:
        collector = LLMMetricsCollector()

        # Start a call
        await collector.start_call("ollama")

        # End a call
        await collector.end_call("ollama", latency=0.5, success=True)

        # Get summary
        summary = collector.get_realtime_summary()
    """

    def __init__(self):
        # Provider-specific metrics
        self._provider_metrics: Dict[str, ProviderMetrics] = {
            "ollama": ProviderMetrics(),
            "openrouter": ProviderMetrics(),
        }

        # Cache metrics
        self._cache_metrics = CacheMetrics()

        # Decision distribution
        self._decision_metrics = DecisionMetrics()

        # Thread safety
        self._lock = asyncio.Lock()

        # Start time for uptime calculation
        self._start_time = time.time()

    async def start_call(self, provider: str) -> None:
        """
        Record the start of an LLM call.

        Args:
            provider: "ollama" or "openrouter"
        """
        async with self._lock:
            metrics = self._provider_metrics.get(provider)
            if not metrics:
                logger.warning(f"Unknown provider: {provider}")
                return

            metrics.current_concurrent += 1
            metrics.max_concurrent = max(
                metrics.max_concurrent, metrics.current_concurrent
            )
            metrics.total_calls += 1

    async def end_call(
        self,
        provider: str,
        latency: float,
        success: bool,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Record the end of an LLM call.

        Args:
            provider: "ollama" or "openrouter"
            latency: Time taken for the call in seconds
            success: Whether the call succeeded
            error_type: Type of error if failed (e.g., "timeout", "connection")
        """
        async with self._lock:
            metrics = self._provider_metrics.get(provider)
            if not metrics:
                logger.warning(f"Unknown provider: {provider}")
                return

            metrics.current_concurrent -= 1
            metrics.latencies.append(latency)

            if not success:
                metrics.error_count += 1
                if error_type:
                    metrics.errors_by_type[error_type] = (
                        metrics.errors_by_type.get(error_type, 0) + 1
                    )

    async def update_queue_depth(self, provider: str, depth: int) -> None:
        """
        Update the queue depth for a provider.

        Args:
            provider: "ollama" or "openrouter"
            depth: Current number of queued requests
        """
        async with self._lock:
            metrics = self._provider_metrics.get(provider)
            if not metrics:
                return

            metrics.queue_depth = depth
            metrics.max_queue_depth = max(metrics.max_queue_depth, depth)

    async def record_cache_hit(self) -> None:
        """Record a cache hit."""
        async with self._lock:
            self._cache_metrics.hits += 1

    async def record_cache_miss(self) -> None:
        """Record a cache miss."""
        async with self._lock:
            self._cache_metrics.misses += 1

    async def record_cache_eviction(self) -> None:
        """Record a cache eviction."""
        async with self._lock:
            self._cache_metrics.evictions += 1

    async def record_llm_decision(self) -> None:
        """Record an LLM-based decision."""
        async with self._lock:
            self._decision_metrics.llm_decisions += 1

    async def record_probability_decision(self) -> None:
        """Record a probability-based decision."""
        async with self._lock:
            self._decision_metrics.probability_decisions += 1

    def _calculate_percentile(self, values: deque, percentile: float) -> float:
        """
        Calculate a percentile from a deque of values.

        Args:
            values: Deque of numeric values
            percentile: Percentile to calculate (0-100)

        Returns:
            The percentile value
        """
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_provider_summary(self, provider: str) -> dict:
        """
        Get metrics summary for a specific provider.

        Args:
            provider: "ollama" or "openrouter"

        Returns:
            Dict with provider metrics
        """
        metrics = self._provider_metrics.get(provider)
        if not metrics:
            return {}

        latencies = list(metrics.latencies)

        return {
            "provider": provider,
            "current_concurrent": metrics.current_concurrent,
            "max_concurrent": metrics.max_concurrent,
            "total_calls": metrics.total_calls,
            "error_count": metrics.error_count,
            "error_rate": metrics.error_count / metrics.total_calls
            if metrics.total_calls > 0
            else 0.0,
            "errors_by_type": dict(metrics.errors_by_type),
            "queue_depth": metrics.queue_depth,
            "max_queue_depth": metrics.max_queue_depth,
            "latency": {
                "p50": self._calculate_percentile(latencies, 50),
                "p95": self._calculate_percentile(latencies, 95),
                "p99": self._calculate_percentile(latencies, 99),
                "avg": sum(latencies) / len(latencies) if latencies else 0.0,
                "min": min(latencies) if latencies else 0.0,
                "max": max(latencies) if latencies else 0.0,
                "count": len(latencies),
            },
        }

    def get_cache_summary(self) -> dict:
        """
        Get cache performance summary.

        Returns:
            Dict with cache metrics
        """
        return {
            "hits": self._cache_metrics.hits,
            "misses": self._cache_metrics.misses,
            "evictions": self._cache_metrics.evictions,
            "total_lookups": self._cache_metrics.total_lookups,
            "hit_rate": self._cache_metrics.hit_rate,
            "hit_rate_percent": f"{self._cache_metrics.hit_rate * 100:.1f}%",
        }

    def get_decision_summary(self) -> dict:
        """
        Get decision distribution summary.

        Returns:
            Dict with decision metrics
        """
        return {
            "llm_decisions": self._decision_metrics.llm_decisions,
            "probability_decisions": self._decision_metrics.probability_decisions,
            "total_decisions": self._decision_metrics.total_decisions,
            "llm_percentage": self._decision_metrics.llm_percentage,
            "llm_percentage_formatted": f"{self._decision_metrics.llm_percentage * 100:.1f}%",
        }

    def get_realtime_summary(self) -> dict:
        """
        Get complete real-time summary of all metrics.

        Returns:
            Dict with all metrics for dashboard display
        """
        uptime = time.time() - self._start_time

        return {
            "timestamp": time.time(),
            "uptime_seconds": uptime,
            "uptime_formatted": f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s",
            "providers": {
                "ollama": self.get_provider_summary("ollama"),
                "openrouter": self.get_provider_summary("openrouter"),
            },
            "cache": self.get_cache_summary(),
            "decisions": self.get_decision_summary(),
        }

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        self._provider_metrics = {
            "ollama": ProviderMetrics(),
            "openrouter": ProviderMetrics(),
        }
        self._cache_metrics = CacheMetrics()
        self._decision_metrics = DecisionMetrics()
        self._start_time = time.time()
        logger.info("Metrics collector reset")


# Global metrics collector instance
_metrics_collector: Optional[LLMMetricsCollector] = None


def get_metrics_collector() -> LLMMetricsCollector:
    """
    Get or create the global metrics collector instance.

    Returns:
        The global LLMMetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = LLMMetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector."""
    global _metrics_collector
    if _metrics_collector:
        _metrics_collector.reset()
    else:
        _metrics_collector = LLMMetricsCollector()
