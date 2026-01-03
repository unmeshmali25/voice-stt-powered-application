"""
Token bucket rate limiter for API calls.

Protects Railway API from overwhelming with 372 concurrent agents.
Provides smooth rate limiting with burst capacity.
"""
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """
    Token bucket rate limiter.

    Thread-safe implementation using asyncio.Lock.
    Refills tokens continuously based on elapsed time.

    Usage:
        limiter = TokenBucket(capacity=50, refill_rate=50.0)
        await limiter.wait_and_acquire()  # Blocks if no tokens available
    """
    capacity: int = 50          # Max burst capacity (tokens)
    refill_rate: float = 50.0   # Tokens added per second

    # Internal state
    tokens: float = field(default=None)
    last_refill: float = field(default=None)
    _lock: asyncio.Lock = field(default=None)

    # Metrics
    total_acquired: int = field(default=0)
    total_waited_ms: float = field(default=0.0)
    max_wait_ms: float = field(default=0.0)

    def __post_init__(self):
        """Initialize mutable defaults after dataclass creation."""
        if self.tokens is None:
            self.tokens = float(self.capacity)
        if self.last_refill is None:
            self.last_refill = time.monotonic()
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, returning wait time required.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            Wait time in seconds (0.0 if tokens immediately available)
        """
        async with self._lock:
            now = time.monotonic()

            # Refill based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                self.total_acquired += tokens
                return 0.0

            # Calculate wait time needed
            wait_time = (tokens - self.tokens) / self.refill_rate
            return wait_time

    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        wait_time = await self.acquire(tokens)
        if wait_time > 0:
            wait_ms = wait_time * 1000
            self.total_waited_ms += wait_ms
            self.max_wait_ms = max(self.max_wait_ms, wait_ms)

            if wait_ms > 100:  # Log significant waits
                logger.debug(f"Rate limiter: waiting {wait_ms:.1f}ms for {tokens} token(s)")

            await asyncio.sleep(wait_time)
            # Re-acquire after waiting (tokens should be available now)
            async with self._lock:
                self.tokens -= tokens
                self.total_acquired += tokens

    def get_metrics(self) -> Dict[str, float]:
        """Get rate limiter metrics."""
        return {
            "current_tokens": round(self.tokens, 2),
            "capacity": self.capacity,
            "refill_rate": self.refill_rate,
            "total_acquired": self.total_acquired,
            "total_waited_ms": round(self.total_waited_ms, 2),
            "max_wait_ms": round(self.max_wait_ms, 2),
        }

    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        self.total_acquired = 0
        self.total_waited_ms = 0.0
        self.max_wait_ms = 0.0


class RateLimiterRegistry:
    """
    Registry of rate limiters for different resources.

    Allows managing multiple rate limiters by name (e.g., 'railway_api', 'database').
    """

    def __init__(self):
        self.limiters: Dict[str, TokenBucket] = {}

    def get_or_create(
        self,
        name: str,
        capacity: int = 50,
        refill_rate: float = 50.0
    ) -> TokenBucket:
        """
        Get existing limiter or create new one.

        Args:
            name: Limiter name (e.g., 'railway_api')
            capacity: Max burst capacity
            refill_rate: Tokens per second

        Returns:
            TokenBucket instance
        """
        if name not in self.limiters:
            self.limiters[name] = TokenBucket(
                capacity=capacity,
                refill_rate=refill_rate
            )
            logger.info(f"Created rate limiter '{name}': {capacity} capacity, {refill_rate} req/s")
        return self.limiters[name]

    def get(self, name: str) -> Optional[TokenBucket]:
        """Get limiter by name, or None if not exists."""
        return self.limiters.get(name)

    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get metrics from all limiters."""
        return {
            name: limiter.get_metrics()
            for name, limiter in self.limiters.items()
        }

    def reset_all_metrics(self) -> None:
        """Reset metrics for all limiters."""
        for limiter in self.limiters.values():
            limiter.reset_metrics()


# Global registry singleton
_registry: Optional[RateLimiterRegistry] = None


def get_registry() -> RateLimiterRegistry:
    """Get the global rate limiter registry."""
    global _registry
    if _registry is None:
        _registry = RateLimiterRegistry()
    return _registry


def get_rate_limiter(
    name: str = "railway_api",
    capacity: int = 50,
    refill_rate: float = 50.0
) -> TokenBucket:
    """
    Get rate limiter by name.

    Convenience function for accessing the global registry.

    Args:
        name: Limiter name (default: 'railway_api')
        capacity: Max burst capacity (default: 50)
        refill_rate: Tokens per second (default: 50.0)

    Returns:
        TokenBucket instance

    Example:
        limiter = get_rate_limiter("railway_api", capacity=50, refill_rate=50.0)
        await limiter.wait_and_acquire()
        # Make API call...
    """
    return get_registry().get_or_create(name, capacity, refill_rate)


def get_rate_limiter_metrics() -> Dict[str, Dict[str, float]]:
    """Get metrics from all rate limiters."""
    return get_registry().get_all_metrics()


def reset_rate_limiter_metrics() -> None:
    """Reset metrics for all rate limiters."""
    get_registry().reset_all_metrics()


def reset_rate_limiters() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None
