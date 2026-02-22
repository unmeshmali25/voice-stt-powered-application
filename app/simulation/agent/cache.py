"""Deterministic cache system for LLM decisions.

Provides caching to reduce redundant LLM calls by storing decisions
based on deterministic context hashing.
"""

import hashlib
import json
import sqlite3
import time
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import asyncio
from contextlib import contextmanager
import threading


@dataclass
class CacheStats:
    """Statistics for cache performance tracking."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_requests: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.misses / self.total_requests) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
        }


class DecisionCache:
    """Deterministic cache for LLM decisions.

    Uses SHA256 hashing of normalized context to create cache keys.
    Stores decisions in SQLite with TTL support.
    """

    def __init__(
        self,
        db_path: str = ".cache/llm_decisions.db",
        default_ttl: int = 3600,
        cleanup_interval: int = 300,
    ):
        """Initialize the decision cache.

        Args:
            db_path: Path to SQLite database file
            default_ttl: Default TTL in seconds (1 hour)
            cleanup_interval: How often to run cleanup in seconds (5 min)
        """
        self.db_path = Path(db_path)
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self.stats = CacheStats()
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with required tables."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    context_hash TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    decision BOOLEAN NOT NULL,
                    confidence REAL,
                    reasoning TEXT,
                    urgency TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    context_json TEXT NOT NULL
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_type 
                ON decisions(agent_id, decision_type)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires 
                ON decisions(expires_at)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with automatic cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()

    def _hash_context(
        self, agent_id: str, decision_type: str, context: Dict[str, Any]
    ) -> str:
        """Create deterministic hash from decision context.

        Normalizes floats to 2 decimal places for consistent hashing
        across slight floating point variations.

        Args:
            agent_id: Unique agent identifier
            decision_type: Type of decision (e.g., 'shop', 'checkout')
            context: Decision context dictionary

        Returns:
            SHA256 hex digest string (64 characters)
        """
        # Create a normalized copy of context
        normalized = self._normalize_value(
            {"agent_id": agent_id, "decision_type": decision_type, "context": context}
        )

        # Convert to canonical JSON string
        # sort_keys ensures consistent ordering
        json_str = json.dumps(normalized, sort_keys=True, separators=(",", ":"))

        # Create SHA256 hash
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def _normalize_value(self, value: Any) -> Any:
        """Recursively normalize values for consistent hashing.

        - Floats: rounded to 2 decimal places
        - Lists: recursively normalize elements
        - Dicts: recursively normalize values
        - Other types: pass through

        Args:
            value: Value to normalize

        Returns:
            Normalized value
        """
        if isinstance(value, float):
            # Normalize to 2 decimal places
            return round(value, 2)
        elif isinstance(value, dict):
            return {k: self._normalize_value(v) for k, v in sorted(value.items())}
        elif isinstance(value, list):
            return [self._normalize_value(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._normalize_value(item) for item in value)
        else:
            return value

    def _maybe_cleanup(self) -> None:
        """Run cleanup if interval has passed."""
        now = time.time()
        if now - self._last_cleanup >= self.cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def _cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM decisions WHERE expires_at < ?", (now,)
                )
                conn.commit()
                evicted = cursor.rowcount
                self.stats.evictions += evicted
                return evicted

    async def get(
        self, agent_id: str, decision_type: str, context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get cached decision for given context.

        Args:
            agent_id: Unique agent identifier
            decision_type: Type of decision
            context: Decision context

        Returns:
            Cached decision dict if found and not expired, None otherwise
        """
        with self._lock:
            self.stats.total_requests += 1

            # Generate hash
            context_hash = self._hash_context(agent_id, decision_type, context)

            # Check for expired entries cleanup
            self._maybe_cleanup()

            # Query database
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT decision, confidence, reasoning, urgency, context_json
                       FROM decisions 
                       WHERE context_hash = ? AND expires_at > ?""",
                    (context_hash, now),
                )
                row = cursor.fetchone()

                if row:
                    self.stats.hits += 1
                    return {
                        "context_hash": context_hash,
                        "decision": bool(row[0]),
                        "confidence": row[1],
                        "reasoning": row[2],
                        "urgency": row[3],
                        "context_json": row[4],
                        "cache_hit": True,
                    }
                else:
                    self.stats.misses += 1
                    return None

    async def set(
        self,
        agent_id: str,
        decision_type: str,
        context: Dict[str, Any],
        decision: bool,
        confidence: Optional[float] = None,
        reasoning: Optional[str] = None,
        urgency: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> str:
        """Store decision in cache.

        Args:
            agent_id: Unique agent identifier
            decision_type: Type of decision
            context: Decision context
            decision: Boolean decision result
            confidence: Optional confidence score (0-1)
            reasoning: Optional reasoning text
            urgency: Optional urgency level
            ttl: TTL in seconds (uses default if not specified)

        Returns:
            Context hash that was used as key
        """
        with self._lock:
            # Generate hash
            context_hash = self._hash_context(agent_id, decision_type, context)

            # Calculate expiration
            ttl = ttl or self.default_ttl
            now = time.time()
            expires_at = now + ttl

            # Store in database
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO decisions 
                       (context_hash, agent_id, decision_type, decision, 
                        confidence, reasoning, urgency, created_at, expires_at, context_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        context_hash,
                        agent_id,
                        decision_type,
                        decision,
                        confidence,
                        reasoning,
                        urgency,
                        now,
                        expires_at,
                        json.dumps(context, sort_keys=True),
                    ),
                )
                conn.commit()

            return context_hash

    def get_stats(self) -> CacheStats:
        """Get current cache statistics.

        Returns:
            CacheStats object with current statistics
        """
        with self._lock:
            return CacheStats(
                hits=self.stats.hits,
                misses=self.stats.misses,
                evictions=self.stats.evictions,
                total_requests=self.stats.total_requests,
            )

    def reset_stats(self) -> None:
        """Reset cache statistics to zero."""
        with self._lock:
            self.stats = CacheStats()

    def clear(self) -> int:
        """Clear all entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM decisions")
                conn.commit()
                return cursor.rowcount

    def get_size(self) -> int:
        """Get current number of entries in cache.

        Returns:
            Number of non-expired entries
        """
        with self._lock:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM decisions WHERE expires_at > ?", (now,)
                )
                return cursor.fetchone()[0]

    def get_entry(self, context_hash: str) -> Optional[Dict[str, Any]]:
        """Get specific entry by hash (for debugging).

        Args:
            context_hash: The hash key to look up

        Returns:
            Entry dict if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT context_hash, agent_id, decision_type, decision,
                          confidence, reasoning, urgency, created_at, expires_at
                   FROM decisions WHERE context_hash = ?""",
                (context_hash,),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "context_hash": row[0],
                    "agent_id": row[1],
                    "decision_type": row[2],
                    "decision": bool(row[3]),
                    "confidence": row[4],
                    "reasoning": row[5],
                    "urgency": row[6],
                    "created_at": row[7],
                    "expires_at": row[8],
                    "expired": time.time() > row[8],
                }
            return None


# Global cache instance for convenience
_cache_instance: Optional[DecisionCache] = None


def get_cache(db_path: str = ".cache/llm_decisions.db") -> DecisionCache:
    """Get or create global cache instance.

    Args:
        db_path: Path to database

    Returns:
        DecisionCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DecisionCache(db_path=db_path)
    return _cache_instance


def reset_cache() -> None:
    """Reset global cache instance."""
    global _cache_instance
    _cache_instance = None
