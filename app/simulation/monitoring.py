"""
Monitoring utilities for scaled simulation.

Provides:
- LatencyTracker: API latency percentiles (p50/p95/p99)
- MemoryMonitor: RAM usage tracking with thresholds
- CircuitBreaker: Pause simulation on excessive failures
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class LatencyStats:
    """Latency percentile statistics."""
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    count: int = 0
    errors: int = 0
    avg: float = 0.0
    min: float = 0.0
    max: float = 0.0


class LatencyTracker:
    """
    Track API latency with sliding window percentiles.

    Maintains a fixed-size window of recent latencies for each endpoint.
    Calculates p50, p95, p99 percentiles on demand.

    Usage:
        tracker = LatencyTracker(window_size=1000)
        tracker.record("checkout", 150.5)  # 150.5ms
        stats = tracker.get_stats("checkout")
    """

    def __init__(self, window_size: int = 1000):
        """
        Initialize latency tracker.

        Args:
            window_size: Max latency samples to keep per endpoint
        """
        self.window_size = window_size
        self.latencies: Dict[str, List[float]] = {}
        self.errors: Dict[str, int] = {}

    def record(self, endpoint: str, latency_ms: float) -> None:
        """
        Record a latency measurement.

        Args:
            endpoint: Endpoint name (e.g., 'checkout', 'browse')
            latency_ms: Latency in milliseconds
        """
        if endpoint not in self.latencies:
            self.latencies[endpoint] = []

        self.latencies[endpoint].append(latency_ms)

        # Trim to window size
        if len(self.latencies[endpoint]) > self.window_size:
            self.latencies[endpoint] = self.latencies[endpoint][-self.window_size:]

    def record_error(self, endpoint: str) -> None:
        """Record an error for endpoint."""
        self.errors[endpoint] = self.errors.get(endpoint, 0) + 1

    def get_stats(self, endpoint: str) -> LatencyStats:
        """
        Get percentile stats for a specific endpoint.

        Args:
            endpoint: Endpoint name

        Returns:
            LatencyStats with percentiles
        """
        if endpoint not in self.latencies or not self.latencies[endpoint]:
            return LatencyStats()

        sorted_latencies = sorted(self.latencies[endpoint])
        count = len(sorted_latencies)

        return LatencyStats(
            p50=sorted_latencies[int(count * 0.50)],
            p95=sorted_latencies[int(count * 0.95)] if count >= 20 else 0.0,
            p99=sorted_latencies[int(count * 0.99)] if count >= 100 else 0.0,
            count=count,
            errors=self.errors.get(endpoint, 0),
            avg=sum(sorted_latencies) / count,
            min=sorted_latencies[0],
            max=sorted_latencies[-1],
        )

    def get_aggregate(self) -> LatencyStats:
        """
        Get aggregate stats across all endpoints.

        Returns:
            LatencyStats with combined percentiles
        """
        all_latencies = []
        total_errors = 0

        for endpoint, latencies in self.latencies.items():
            all_latencies.extend(latencies)
            total_errors += self.errors.get(endpoint, 0)

        if not all_latencies:
            return LatencyStats()

        sorted_latencies = sorted(all_latencies)
        count = len(sorted_latencies)

        return LatencyStats(
            p50=sorted_latencies[int(count * 0.50)],
            p95=sorted_latencies[int(count * 0.95)] if count >= 20 else 0.0,
            p99=sorted_latencies[int(count * 0.99)] if count >= 100 else 0.0,
            count=count,
            errors=total_errors,
            avg=sum(sorted_latencies) / count,
            min=sorted_latencies[0],
            max=sorted_latencies[-1],
        )

    def get_all_endpoints(self) -> Dict[str, LatencyStats]:
        """Get stats for all tracked endpoints."""
        return {
            endpoint: self.get_stats(endpoint)
            for endpoint in self.latencies.keys()
        }

    def reset(self) -> None:
        """Clear all tracked data."""
        self.latencies.clear()
        self.errors.clear()


class MemoryMonitor:
    """
    Track memory usage during simulation.

    Uses psutil if available, gracefully degrades if not installed.

    Usage:
        monitor = MemoryMonitor(warning_threshold_mb=12000)
        if not monitor.is_safe():
            print("Memory warning!")
        print(f"Usage: {monitor.get_usage_mb():.1f} MB")
    """

    def __init__(self, warning_threshold_mb: int = 12000):
        """
        Initialize memory monitor.

        Args:
            warning_threshold_mb: Threshold for warnings (default: 12GB)
        """
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Convert to bytes

        try:
            import psutil
            self.psutil = psutil
            self.process = psutil.Process(os.getpid())
            self.available = True
        except ImportError:
            self.psutil = None
            self.process = None
            self.available = False
            logger.warning("psutil not installed - memory monitoring disabled. Install with: pip install psutil")

    def get_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        if not self.available:
            return 0.0
        return self.process.memory_info().rss / 1024 / 1024

    def is_safe(self) -> bool:
        """Return True if memory is below warning threshold."""
        if not self.available:
            return True
        return self.process.memory_info().rss < self.warning_threshold

    def get_stats(self) -> Dict[str, Any]:
        """Get detailed memory stats."""
        if not self.available:
            return {"available": False}

        mem = self.process.memory_info()
        return {
            "available": True,
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
            "percent": round(self.process.memory_percent(), 1),
            "threshold_mb": self.warning_threshold / 1024 / 1024,
            "is_safe": self.is_safe(),
        }


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Paused due to excessive errors


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold_percent: float = 5.0  # 5% of agents
    window_type: str = "per_cycle"  # per_cycle or rolling


class CircuitBreaker:
    """
    Circuit breaker that pauses simulation on excessive failures.

    Triggers when >5% of agents fail in a single cycle.
    Requires manual reset via keyboard shortcut or API.

    Usage:
        cb = CircuitBreaker(total_agents=372)

        for agent in agents:
            try:
                result = execute_agent(agent)
                cb.record_success()
            except Exception as e:
                cb.record_failure(agent.id, e)

        if cb.is_open():
            print("Circuit breaker triggered!")

        # At end of cycle
        cb.reset_cycle()
    """

    def __init__(
        self,
        total_agents: int,
        config: Optional[CircuitBreakerConfig] = None,
        on_open_callback: Optional[Callable] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            total_agents: Total number of agents in simulation
            config: Configuration options
            on_open_callback: Async callback when circuit opens
        """
        self.config = config or CircuitBreakerConfig()
        self.total_agents = total_agents
        self.on_open_callback = on_open_callback

        self.state = CircuitState.CLOSED
        self.cycle_failures = 0
        self.total_failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        self.failure_details: List[Dict[str, Any]] = []

        # Calculate threshold
        self.failure_threshold = max(1, int(
            total_agents * (self.config.failure_threshold_percent / 100)
        ))

        logger.info(
            f"Circuit breaker initialized: threshold={self.failure_threshold} "
            f"({self.config.failure_threshold_percent}% of {total_agents} agents)"
        )

    def record_failure(self, agent_id: str, error: Exception) -> None:
        """
        Record an agent failure.

        Args:
            agent_id: ID of failed agent
            error: The exception that occurred
        """
        self.cycle_failures += 1
        self.total_failures += 1
        self.last_failure_time = datetime.now()

        # Keep last 10 failure details
        self.failure_details.append({
            "agent_id": agent_id,
            "error": str(error)[:200],
            "time": datetime.now().isoformat(),
        })
        if len(self.failure_details) > 10:
            self.failure_details.pop(0)

        logger.warning(f"Agent {agent_id} failed: {error}")

        # Check threshold
        if self.cycle_failures > self.failure_threshold and self.state == CircuitState.CLOSED:
            self._open_circuit()

    def record_success(self) -> None:
        """Record successful agent execution."""
        pass  # Success doesn't affect circuit state

    def reset_cycle(self) -> None:
        """Reset failure count for new cycle."""
        self.cycle_failures = 0

    def is_open(self) -> bool:
        """Check if circuit is open (simulation paused)."""
        return self.state == CircuitState.OPEN

    def manual_reset(self) -> None:
        """Manually reset circuit breaker (resume simulation)."""
        prev_state = self.state
        self.state = CircuitState.CLOSED
        self.cycle_failures = 0
        self.opened_at = None

        if prev_state == CircuitState.OPEN:
            logger.info("Circuit breaker manually reset - resuming simulation")

    def _open_circuit(self) -> None:
        """Open the circuit breaker (pause simulation)."""
        self.state = CircuitState.OPEN
        self.opened_at = datetime.now()

        logger.error(
            f"CIRCUIT BREAKER OPEN: {self.cycle_failures} failures "
            f"exceeded threshold of {self.failure_threshold}"
        )

        if self.on_open_callback:
            # Schedule callback asynchronously
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.on_open_callback(self))
                else:
                    loop.run_until_complete(self.on_open_callback(self))
            except RuntimeError:
                # No event loop available
                logger.warning("Could not run circuit breaker callback - no event loop")

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state.value,
            "cycle_failures": self.cycle_failures,
            "threshold": self.failure_threshold,
            "threshold_percent": self.config.failure_threshold_percent,
            "total_failures": self.total_failures,
            "total_agents": self.total_agents,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "recent_failures": self.failure_details[-5:] if self.failure_details else [],
        }

    def update_agent_count(self, total_agents: int) -> None:
        """Update total agent count (e.g., during warmup)."""
        self.total_agents = total_agents
        self.failure_threshold = max(1, int(
            total_agents * (self.config.failure_threshold_percent / 100)
        ))
