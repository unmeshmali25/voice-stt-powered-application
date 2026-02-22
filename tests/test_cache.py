"""Unit tests for deterministic cache system."""

import asyncio
import os
import pytest
import tempfile
import time
from pathlib import Path

from app.simulation.agent.cache import DecisionCache, CacheStats, get_cache, reset_cache


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_stats_initialization(self):
        """Test stats start at zero."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.total_requests == 0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25, total_requests=100)
        assert stats.hit_rate == 75.0
        assert stats.miss_rate == 25.0

    def test_hit_rate_zero_requests(self):
        """Test hit rate with zero requests."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 0.0

    def test_to_dict(self):
        """Test stats conversion to dict."""
        stats = CacheStats(hits=50, misses=50, evictions=10, total_requests=100)
        d = stats.to_dict()
        assert d["hits"] == 50
        assert d["misses"] == 50
        assert d["evictions"] == 10
        assert d["total_requests"] == 100
        assert d["hit_rate"] == 50.0
        assert d["miss_rate"] == 50.0


class TestDecisionCache:
    """Tests for DecisionCache class."""

    @pytest.fixture
    def temp_cache(self):
        """Create a temporary cache for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_cache.db"
            cache = DecisionCache(
                db_path=str(db_path),
                default_ttl=3600,
                cleanup_interval=1,  # Short interval for testing
            )
            yield cache

    def test_cache_initialization(self, temp_cache):
        """Test cache can be initialized."""
        assert temp_cache is not None
        assert temp_cache.db_path.exists()
        assert temp_cache.default_ttl == 3600

    def test_hash_context_deterministic(self, temp_cache):
        """Test that same context produces same hash."""
        context = {"budget": 100.0, "category": "food"}

        hash1 = temp_cache._hash_context("agent_1", "shop", context)
        hash2 = temp_cache._hash_context("agent_1", "shop", context)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length

    def test_hash_context_different_inputs(self, temp_cache):
        """Test that different inputs produce different hashes."""
        context = {"budget": 100.0}

        hash1 = temp_cache._hash_context("agent_1", "shop", context)
        hash2 = temp_cache._hash_context("agent_2", "shop", context)
        hash3 = temp_cache._hash_context("agent_1", "checkout", context)

        assert hash1 != hash2  # Different agent
        assert hash1 != hash3  # Different decision type

    def test_float_normalization(self, temp_cache):
        """Test floats are normalized to 2 decimal places."""
        # These should produce the same hash after normalization
        context1 = {"price": 10.333}
        context2 = {"price": 10.334}
        context3 = {"price": 10.33}

        hash1 = temp_cache._hash_context("agent", "shop", context1)
        hash2 = temp_cache._hash_context("agent", "shop", context2)
        hash3 = temp_cache._hash_context("agent", "shop", context3)

        # Both should round to 10.33
        assert hash1 == hash2
        assert hash1 == hash3

    def test_normalize_value_recursive(self, temp_cache):
        """Test normalization works recursively on nested structures."""
        value = {
            "level1": {
                "level2": {"float_val": 3.14159, "list_val": [1.111, 2.222, 3.333]}
            }
        }

        normalized = temp_cache._normalize_value(value)

        assert normalized["level1"]["level2"]["float_val"] == 3.14
        assert normalized["level1"]["level2"]["list_val"] == [1.11, 2.22, 3.33]

    @pytest.mark.asyncio
    async def test_cache_miss(self, temp_cache):
        """Test cache miss returns None."""
        context = {"budget": 100.0}

        result = await temp_cache.get("agent_1", "shop", context)

        assert result is None
        assert temp_cache.stats.misses == 1
        assert temp_cache.stats.total_requests == 1

    @pytest.mark.asyncio
    async def test_cache_hit(self, temp_cache):
        """Test cache hit returns stored decision."""
        context = {"budget": 100.0}

        # Store decision
        await temp_cache.set(
            agent_id="agent_1",
            decision_type="shop",
            context=context,
            decision=True,
            confidence=0.85,
            reasoning="High budget",
            urgency="medium",
        )

        # Retrieve decision
        result = await temp_cache.get("agent_1", "shop", context)

        assert result is not None
        assert result["decision"] is True
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "High budget"
        assert result["urgency"] == "medium"
        assert result["cache_hit"] is True
        assert temp_cache.stats.hits == 1
        assert temp_cache.stats.misses == 0

    @pytest.mark.asyncio
    async def test_cache_expiration(self, temp_cache):
        """Test entries expire after TTL."""
        context = {"budget": 100.0}

        # Store with 1 second TTL
        await temp_cache.set(
            agent_id="agent_1",
            decision_type="shop",
            context=context,
            decision=True,
            ttl=1,  # 1 second
        )

        # Should be available immediately
        result = await temp_cache.get("agent_1", "shop", context)
        assert result is not None

        # Wait for expiration
        time.sleep(2)

        # Should be expired now
        result = await temp_cache.get("agent_1", "shop", context)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_size(self, temp_cache):
        """Test cache size tracking."""
        # Should start empty
        assert temp_cache.get_size() == 0

        # Add entry
        await temp_cache.set(
            agent_id="agent_1",
            decision_type="shop",
            context={"budget": 100},
            decision=True,
        )

        assert temp_cache.get_size() == 1

        # Add another
        await temp_cache.set(
            agent_id="agent_2",
            decision_type="shop",
            context={"budget": 200},
            decision=False,
        )

        assert temp_cache.get_size() == 2

    @pytest.mark.asyncio
    async def test_cache_clear(self, temp_cache):
        """Test clearing cache."""
        # Add entries
        for i in range(3):
            await temp_cache.set(
                agent_id=f"agent_{i}",
                decision_type="shop",
                context={"id": i},
                decision=True,
            )

        assert temp_cache.get_size() == 3

        # Clear cache
        removed = temp_cache.clear()

        assert removed == 3
        assert temp_cache.get_size() == 0

    @pytest.mark.asyncio
    async def test_cache_update_existing(self, temp_cache):
        """Test updating existing entry."""
        context = {"budget": 100.0}

        # Store initial decision
        await temp_cache.set(
            agent_id="agent_1", decision_type="shop", context=context, decision=True
        )

        # Update with different decision
        await temp_cache.set(
            agent_id="agent_1", decision_type="shop", context=context, decision=False
        )

        # Should retrieve updated value
        result = await temp_cache.get("agent_1", "shop", context)
        assert result["decision"] is False

        # Size should still be 1
        assert temp_cache.get_size() == 1

    def test_get_stats(self, temp_cache):
        """Test getting cache statistics."""
        # Manually set some stats
        temp_cache.stats.hits = 10
        temp_cache.stats.misses = 5
        temp_cache.stats.total_requests = 15

        stats = temp_cache.get_stats()

        assert stats.hits == 10
        assert stats.misses == 5
        assert stats.total_requests == 15
        assert stats.hit_rate == (10 / 15) * 100

    def test_reset_stats(self, temp_cache):
        """Test resetting statistics."""
        temp_cache.stats.hits = 100
        temp_cache.stats.misses = 50

        temp_cache.reset_stats()

        assert temp_cache.stats.hits == 0
        assert temp_cache.stats.misses == 0
        assert temp_cache.stats.total_requests == 0

    @pytest.mark.asyncio
    async def test_get_entry_by_hash(self, temp_cache):
        """Test retrieving entry by hash."""
        context = {"budget": 100.0}

        # Store decision
        context_hash = await temp_cache.set(
            agent_id="agent_1",
            decision_type="shop",
            context=context,
            decision=True,
            confidence=0.9,
        )

        # Retrieve by hash
        entry = temp_cache.get_entry(context_hash)

        assert entry is not None
        assert entry["agent_id"] == "agent_1"
        assert entry["decision_type"] == "shop"
        assert entry["decision"] is True
        assert entry["confidence"] == 0.9
        assert entry["expired"] is False

    def test_get_entry_nonexistent(self, temp_cache):
        """Test retrieving non-existent entry."""
        entry = temp_cache.get_entry("nonexistent_hash")
        assert entry is None


class TestGlobalCache:
    """Tests for global cache instance functions."""

    def test_get_cache_creates_instance(self):
        """Test get_cache creates new instance."""
        reset_cache()  # Clear any existing instance

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "global_cache.db"
            cache = get_cache(str(db_path))

            assert cache is not None
            assert isinstance(cache, DecisionCache)

    def test_get_cache_returns_same_instance(self):
        """Test get_cache returns same instance on subsequent calls."""
        reset_cache()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "global_cache.db"
            cache1 = get_cache(str(db_path))
            cache2 = get_cache(str(db_path))

            assert cache1 is cache2

    def test_reset_cache(self):
        """Test reset_cache clears instance."""
        reset_cache()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "global_cache.db"
            cache1 = get_cache(str(db_path))
            reset_cache()
            cache2 = get_cache(str(db_path))

            assert cache1 is not cache2


class TestCacheCleanup:
    """Tests for cache cleanup functionality."""

    @pytest.fixture
    def temp_cache(self):
        """Create a temporary cache with short cleanup interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_cache.db"
            cache = DecisionCache(
                db_path=str(db_path),
                default_ttl=1,  # 1 second TTL
                cleanup_interval=0.5,  # Cleanup every 0.5 seconds
            )
            yield cache

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired(self, temp_cache):
        """Test cleanup removes expired entries."""
        # Add expired entry
        await temp_cache.set(
            agent_id="agent_1",
            decision_type="shop",
            context={"id": 1},
            decision=True,
            ttl=1,
        )

        # Wait for expiration
        time.sleep(2)

        # Trigger cleanup
        evicted = temp_cache._cleanup_expired()

        assert evicted >= 1
        assert temp_cache.get_size() == 0

    @pytest.mark.asyncio
    async def test_maybe_cleanup_on_access(self, temp_cache):
        """Test cleanup runs automatically on access."""
        # Add entry
        await temp_cache.set(
            agent_id="agent_1",
            decision_type="shop",
            context={"id": 1},
            decision=True,
            ttl=1,
        )

        # Wait for expiration
        time.sleep(2)

        # Access should trigger cleanup
        await temp_cache.get("agent_1", "shop", {"id": 1})

        # Expired entry should be gone
        assert temp_cache.get_size() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
