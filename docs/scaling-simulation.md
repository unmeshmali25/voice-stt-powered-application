# Scaling Simulation: 372 Agents Implementation Plan

> **Target**: Scale from 10 concurrent agents to 372 agents with full parallelization
> **Infrastructure**: MacBook Pro M-series (8-12 cores, 16GB RAM) → Supabase Pro → Railway FastAPI

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Database Connection Strategy](#database-connection-strategy)
4. [API Rate Limiting](#api-rate-limiting)
5. [Parallelization Strategy](#parallelization-strategy)
6. [Memory Management](#memory-management)
7. [Checkpoint & Resume](#checkpoint--resume)
8. [Monitoring & Control](#monitoring--control)
9. [Error Handling & Circuit Breaker](#error-handling--circuit-breaker)
10. [Implementation Priority & Phases](#implementation-priority--phases)
11. [Configuration Reference](#configuration-reference)
12. [Future Roadmap: 1000+ Agents](#future-roadmap-1000-agents)

---

## Executive Summary

### Key Constraints

| Resource | Limit | Strategy |
|----------|-------|----------|
| Local CPU | 8-12 cores | Hybrid async (I/O async, compute sync) |
| Local RAM | 16GB | Load all agents upfront, efficient state management |
| Supabase connections | 100 direct (Pro tier) | Supavisor Transaction Mode pooling |
| Railway API | ~50 req/s conservative | Token bucket rate limiter |
| Cycle time | 75 seconds (time-scale 48) | Sequential steps per agent, parallel agents |

### Throughput Calculation

```
Time-scale 48:
├── Cycle interval = 3600s / 48 = 75 seconds per cycle
├── Active agents per cycle ≈ 40% of 372 = ~150 agents (realistic distribution)
├── API calls per active agent = ~6 calls (browse, cart, coupons, checkout)
├── Total API calls per cycle = 150 × 6 = 900 calls
├── At 50 req/s = 18 seconds for API work
├── Buffer = 75 - 18 = 57 seconds margin ✓
└── Cycles per hour = 48 → 48 cycles × ~150 active = ~7,200 shopping sessions/hour
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LOCAL MACHINE (MacBook Pro)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SimulationOrchestrator (Enhanced)                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │ TimeService  │  │ RateLimiter  │  │  CheckpointManager       │  │   │
│  │  │ (scaled)     │  │ (token bucket)│  │  (cycle-based JSON)     │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  │                                                                      │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │                   Agent Executor Pool                          │ │   │
│  │  │  ┌────────────────────────────────────────────────────────┐   │ │   │
│  │  │  │ asyncio.gather() - 372 concurrent agent coroutines     │   │ │   │
│  │  │  │                                                         │   │ │   │
│  │  │  │  Agent 1 ─┬─ decide_shop                               │   │ │   │
│  │  │  │           ├─ browse_products (async HTTP)              │   │ │   │
│  │  │  │           ├─ add_to_cart (async HTTP + DB)             │   │ │   │
│  │  │  │           ├─ view_coupons (async HTTP)                 │   │ │   │
│  │  │  │           └─ checkout/abandon (async HTTP + DB commit) │   │ │   │
│  │  │  │                                                         │   │ │   │
│  │  │  │  Agent 2 ─┬─ ... (parallel)                            │   │ │   │
│  │  │  │  ...                                                    │   │ │   │
│  │  │  │  Agent 372 ─┬─ ... (parallel)                          │   │ │   │
│  │  │  └────────────────────────────────────────────────────────┘   │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                      │   │
│  │  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │   │
│  │  │ CircuitBreaker      │  │ HTTP Session Pool (10 sessions)     │  │   │
│  │  │ (5% per-cycle)      │  │ Static assignment by agent_id hash  │  │   │
│  │  └─────────────────────┘  └─────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        Monitoring Layer                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐   │  │
│  │  │ Rich Dashboard  │  │ Latency Tracker │  │ Keyboard Control   │   │  │
│  │  │ (5s refresh)    │  │ (p50/p95/p99)   │  │ (p/r/q shortcuts)  │   │  │
│  │  └─────────────────┘  └─────────────────┘  └────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
        ┌───────────────────┐  ┌──────────────┐  ┌────────────────────┐
        │  Supabase Pro     │  │  Railway     │  │  Local Files       │
        │  (PostgreSQL)     │  │  FastAPI     │  │  ./data/checkpoints│
        │                   │  │              │  │                    │
        │  Supavisor Pool   │  │  Cart API    │  │  checkpoint_N.json │
        │  Transaction Mode │  │  Order API   │  │  simulation_errors │
        │  50 pool / 75 max │  │  Offer API   │  │  .log              │
        └───────────────────┘  └──────────────┘  └────────────────────┘
```

---

## Database Connection Strategy

### Supabase Configuration

**Recommended: Supavisor Transaction Mode**

Transaction mode is optimal for this use case because:
- High connection reuse (372 agents, ~100 connections)
- Short-lived transactions (per-agent commits)
- No need for prepared statements or session variables in simulation

```python
# Connection string for transaction mode pooler
DATABASE_URL = "postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?pgbouncer=true"
```

### SQLAlchemy Pool Configuration

```python
# app/database.py - Updated for 372 agents
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=50,           # Base pool size (up from 5)
    max_overflow=75,        # Additional connections under load (up from 10)
    pool_timeout=30,        # Wait time before connection timeout
    pool_recycle=1800,      # Recycle connections every 30 min
    pool_pre_ping=True,     # Verify connection health

    # Transaction mode specific
    pool_reset_on_return='rollback',  # Clean state on return
    echo=False,                        # Disable SQL logging for performance
)
```

### Connection Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    Per-Agent Commit Pattern                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  async def execute_agent(agent_id, db_pool):                   │
│      async with db_pool.acquire() as conn:  # Get from pool    │
│          try:                                                   │
│              # Agent shopping workflow                          │
│              session = create_session(conn, agent_id)          │
│              events = browse_products(conn, session)           │
│              cart_ops = add_to_cart(conn, session)             │
│              coupon_ops = apply_coupons(conn, session)         │
│              order = checkout(conn, session)                   │
│                                                                 │
│              await conn.commit()  # Per-agent commit           │
│          except Exception as e:                                 │
│              await conn.rollback()                              │
│              raise AgentError(agent_id, e)                     │
│      # Connection returned to pool automatically               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Write Optimization

```python
# Batch event recording (reduce round-trips)
async def record_events_batch(conn, events: list[dict]):
    """Insert multiple events in single statement"""
    await conn.execute(
        insert(shopping_session_events).values(events)
    )

# Use COPY for bulk data (future optimization)
# For checkpoint replay, use COPY FROM for massive inserts
```

---

## API Rate Limiting

### Token Bucket Implementation

```python
# app/simulation/rate_limiter.py

import asyncio
import time
from dataclasses import dataclass

@dataclass
class TokenBucket:
    """Token bucket rate limiter for API calls"""

    capacity: int = 50          # Max tokens (requests per second)
    refill_rate: float = 50.0   # Tokens added per second
    tokens: float = 50.0        # Current tokens
    last_refill: float = None
    _lock: asyncio.Lock = None

    def __post_init__(self):
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary.
        Returns wait time in seconds.
        """
        async with self._lock:
            now = time.monotonic()

            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            # Calculate wait time
            wait_time = (tokens - self.tokens) / self.refill_rate
            return wait_time

    async def wait_and_acquire(self, tokens: int = 1):
        """Acquire tokens, blocking until available"""
        wait_time = await self.acquire(tokens)
        if wait_time > 0:
            await asyncio.sleep(wait_time)


# Global rate limiter instance
api_rate_limiter = TokenBucket(capacity=50, refill_rate=50.0)
```

### Rate-Limited API Client

```python
# app/simulation/api_client.py

class RateLimitedAPIClient:
    """HTTP client with built-in rate limiting"""

    def __init__(
        self,
        base_url: str,
        rate_limiter: TokenBucket,
        session_pool_size: int = 10
    ):
        self.base_url = base_url
        self.rate_limiter = rate_limiter
        self.sessions: list[aiohttp.ClientSession] = []
        self.session_pool_size = session_pool_size

    async def initialize(self):
        """Create session pool"""
        connector = aiohttp.TCPConnector(
            limit_per_host=50,  # Max connections per host
            keepalive_timeout=30,
        )
        for _ in range(self.session_pool_size):
            session = aiohttp.ClientSession(
                base_url=self.base_url,
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            self.sessions.append(session)

    def get_session(self, agent_id: str) -> aiohttp.ClientSession:
        """Get session by agent ID hash (consistent assignment)"""
        idx = hash(agent_id) % len(self.sessions)
        return self.sessions[idx]

    async def request(
        self,
        method: str,
        endpoint: str,
        agent_id: str,
        **kwargs
    ) -> dict:
        """Make rate-limited API request"""
        await self.rate_limiter.wait_and_acquire()

        session = self.get_session(agent_id)
        start_time = time.monotonic()

        try:
            async with session.request(method, endpoint, **kwargs) as resp:
                latency = time.monotonic() - start_time
                latency_tracker.record(endpoint, latency)

                if resp.status == 429:
                    # Rate limited by server, back off
                    retry_after = float(resp.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await self.request(method, endpoint, agent_id, **kwargs)

                return await resp.json()
        except Exception as e:
            latency_tracker.record_error(endpoint)
            raise
```

---

## Parallelization Strategy

### Hybrid Async Model

**Approach**: Async I/O operations, synchronous compute (LangGraph decisions)

```python
# app/simulation/parallel_executor.py

import asyncio
from concurrent.futures import ThreadPoolExecutor

class ParallelAgentExecutor:
    """Execute 372 agents in parallel with hybrid async model"""

    def __init__(
        self,
        agents: list[Agent],
        api_client: RateLimitedAPIClient,
        db_pool: AsyncConnectionPool,
        max_workers: int = 12  # Match CPU cores
    ):
        self.agents = agents
        self.api_client = api_client
        self.db_pool = db_pool
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    async def execute_cycle(self, simulated_time: datetime) -> CycleResult:
        """Execute all agents for one cycle"""

        # Create coroutines for all agents
        tasks = [
            self.execute_agent(agent, simulated_time)
            for agent in self.agents
        ]

        # Run all agents concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successes = []
        failures = []
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                failures.append((agent.id, result))
            else:
                successes.append(result)

        return CycleResult(
            successes=successes,
            failures=failures,
            timestamp=simulated_time
        )

    async def execute_agent(
        self,
        agent: Agent,
        simulated_time: datetime
    ) -> AgentResult:
        """Execute single agent with hybrid async/sync"""

        # Check if agent should shop (temporal preferences)
        should_shop = self._should_agent_shop(agent, simulated_time)

        if not should_shop:
            # Idle agents still browse (generates events)
            return await self._execute_idle_browsing(agent, simulated_time)

        # Get database connection from pool
        async with self.db_pool.acquire() as conn:
            try:
                # Sync compute: LangGraph decision making
                # Run in thread pool to not block event loop
                loop = asyncio.get_event_loop()
                state = await loop.run_in_executor(
                    self.thread_pool,
                    self._run_langgraph_sync,
                    agent,
                    simulated_time
                )

                # Async I/O: API calls and DB writes
                if state.decision == 'shop':
                    result = await self._execute_shopping_flow(
                        agent, state, conn, simulated_time
                    )
                else:
                    result = AgentResult(agent.id, action='skipped')

                # Per-agent commit
                await conn.commit()
                return result

            except Exception as e:
                await conn.rollback()
                raise AgentExecutionError(agent.id, e)

    def _should_agent_shop(
        self,
        agent: Agent,
        simulated_time: datetime
    ) -> bool:
        """Check temporal preferences for shopping"""
        hour = simulated_time.hour
        day_of_week = simulated_time.weekday()

        # Apply time-of-day affinity
        time_affinity = agent.get_time_affinity(hour)

        # Apply day-of-week affinity
        if day_of_week < 5:  # Weekday
            day_affinity = agent.weekday_affinity
        else:  # Weekend
            day_affinity = agent.weekend_affinity

        # Combined probability
        probability = agent.shopping_frequency * time_affinity * day_affinity
        return random.random() < probability
```

### Warm-up Ramp-up Strategy

```python
# Configurable warm-up period

class WarmupController:
    """Gradually ramp up agent count"""

    def __init__(
        self,
        total_agents: int,
        warmup_cycles: int = 10,
        warmup_batches: list[float] = None
    ):
        self.total_agents = total_agents
        self.warmup_cycles = warmup_cycles
        self.warmup_batches = warmup_batches or [0.1, 0.25, 0.5, 0.75, 1.0]
        self.current_cycle = 0

    def get_active_agent_count(self) -> int:
        """Get number of agents for current cycle"""
        if self.current_cycle >= self.warmup_cycles:
            return self.total_agents

        progress = self.current_cycle / self.warmup_cycles

        # Find appropriate batch
        for threshold in self.warmup_batches:
            if progress <= threshold:
                return int(self.total_agents * threshold)

        return self.total_agents

    def advance(self):
        self.current_cycle += 1

# Usage:
# Cycle 0-1: 37 agents (10%)
# Cycle 2-3: 93 agents (25%)
# Cycle 4-5: 186 agents (50%)
# Cycle 6-7: 279 agents (75%)
# Cycle 8+: 372 agents (100%)
```

---

## Memory Management

### Agent State Efficiency

```python
# Estimated memory per agent
#
# Agent persona: ~2KB (attributes, preferences)
# Session state: ~1KB (cart items, viewed products)
# LangGraph state: ~500B
# Buffers: ~500B
# Total: ~4KB per agent
#
# 372 agents × 4KB = ~1.5MB (negligible)

# However, HTTP connections and async tasks add overhead:
# - aiohttp session: ~100KB per session × 10 sessions = 1MB
# - asyncio task overhead: ~10KB per task × 372 = 3.7MB
# - Database connection pool: ~5KB per conn × 50 = 250KB
# - Buffers and caches: ~50MB
#
# Total estimated: ~60MB active memory (well within 16GB)
```

### Memory Monitoring

```python
import psutil
import os

class MemoryMonitor:
    """Track memory usage during simulation"""

    def __init__(self, warning_threshold_mb: int = 12000):
        self.process = psutil.Process(os.getpid())
        self.warning_threshold = warning_threshold_mb * 1024 * 1024

    def get_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024

    def check_threshold(self) -> bool:
        """Return True if memory is safe"""
        return self.process.memory_info().rss < self.warning_threshold

    def get_stats(self) -> dict:
        """Get detailed memory stats"""
        mem = self.process.memory_info()
        return {
            'rss_mb': mem.rss / 1024 / 1024,
            'vms_mb': mem.vms / 1024 / 1024,
            'percent': self.process.memory_percent(),
        }
```

---

## Checkpoint & Resume

### Checkpoint File Structure

```json
// ./data/checkpoints/checkpoint_2024-01-15_cycle_48.json
{
    "version": "1.0",
    "created_at": "2024-01-15T10:30:00Z",
    "simulation_config": {
        "time_scale": 48,
        "total_agents": 372,
        "rate_limit_rps": 50
    },
    "simulation_state": {
        "current_cycle": 48,
        "simulated_datetime": "2024-01-03T12:00:00",
        "real_elapsed_seconds": 3600,
        "is_replay": false
    },
    "statistics": {
        "total_sessions": 3456,
        "total_checkouts": 1234,
        "total_errors": 12,
        "cycles_completed": 48
    },
    "agent_states": {
        "agent_001": {
            "last_cycle_completed": 48,
            "last_action": "checkout",
            "shopping_this_cycle": true
        },
        // ... 371 more agents
    },
    "offer_engine_state": {
        "current_offer_cycle": 2,
        "cycle_started_at": "2024-01-01T00:00:00",
        "cycle_ends_at": "2024-01-08T00:00:00"
    }
}
```

### Checkpoint Manager

```python
# app/simulation/checkpoint.py

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class CheckpointData:
    version: str = "1.0"
    created_at: str = None
    simulation_config: dict = None
    simulation_state: dict = None
    statistics: dict = None
    agent_states: dict = None
    offer_engine_state: dict = None


class CheckpointManager:
    """Manage simulation checkpoints"""

    def __init__(
        self,
        checkpoint_dir: Path = Path("./data/checkpoints"),
        save_interval_cycles: int = 10
    ):
        self.checkpoint_dir = checkpoint_dir
        self.save_interval_cycles = save_interval_cycles
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def should_save(self, cycle: int) -> bool:
        """Check if checkpoint should be saved this cycle"""
        return cycle > 0 and cycle % self.save_interval_cycles == 0

    async def save(
        self,
        orchestrator: 'SimulationOrchestrator',
        cycle: int
    ) -> Path:
        """Save checkpoint after cycle completes"""

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"checkpoint_{timestamp}_cycle_{cycle}.json"
        filepath = self.checkpoint_dir / filename

        data = CheckpointData(
            created_at=datetime.now().isoformat(),
            simulation_config={
                "time_scale": orchestrator.time_scale,
                "total_agents": len(orchestrator.agents),
                "rate_limit_rps": orchestrator.rate_limiter.capacity,
            },
            simulation_state={
                "current_cycle": cycle,
                "simulated_datetime": orchestrator.time_service.now().isoformat(),
                "real_elapsed_seconds": orchestrator.elapsed_seconds,
                "is_replay": False,
            },
            statistics=asdict(orchestrator.stats),
            agent_states={
                agent.id: {
                    "last_cycle_completed": cycle,
                    "last_action": agent.last_action,
                    "shopping_this_cycle": agent.shopped_this_cycle,
                }
                for agent in orchestrator.agents
            },
            offer_engine_state=orchestrator.scheduler.get_state_dict(),
        )

        # Atomic write (write to temp, then rename)
        temp_path = filepath.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(asdict(data), f, indent=2)
        temp_path.rename(filepath)

        # Clean old checkpoints (keep last 5)
        self._cleanup_old_checkpoints()

        return filepath

    def find_latest(self) -> Path | None:
        """Find most recent checkpoint file"""
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return checkpoints[0] if checkpoints else None

    async def load(self, filepath: Path) -> CheckpointData:
        """Load checkpoint from file"""
        with open(filepath) as f:
            data = json.load(f)
        return CheckpointData(**data)

    async def resume(
        self,
        filepath: Path,
        orchestrator: 'SimulationOrchestrator'
    ):
        """Resume simulation from checkpoint"""
        data = await self.load(filepath)

        # Restore state
        orchestrator.current_cycle = data.simulation_state['current_cycle']
        orchestrator.time_service.set_simulated_time(
            datetime.fromisoformat(data.simulation_state['simulated_datetime'])
        )
        orchestrator.elapsed_seconds = data.simulation_state['real_elapsed_seconds']

        # Mark this run as replay
        orchestrator.is_replay = True

        # Clean up orphaned sessions
        await self._cleanup_orphaned_sessions(orchestrator.db)

        return data

    async def _cleanup_orphaned_sessions(self, db):
        """Clean up sessions left in active state from crash"""
        result = await db.execute("""
            UPDATE shopping_sessions
            SET status = 'abandoned',
                ended_at = NOW(),
                notes = 'Auto-abandoned: orphaned from simulation crash'
            WHERE status = 'active'
              AND is_simulated = true
            RETURNING id
        """)
        orphaned = result.fetchall()
        if orphaned:
            logger.info(f"Cleaned up {len(orphaned)} orphaned sessions")

        # Clear orphaned carts
        await db.execute("""
            DELETE FROM cart_items
            WHERE user_id IN (
                SELECT user_id FROM agents WHERE status = 'active'
            )
        """)
        await db.commit()

    def _cleanup_old_checkpoints(self, keep: int = 5):
        """Remove old checkpoint files, keeping most recent"""
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_checkpoint in checkpoints[keep:]:
            old_checkpoint.unlink()
```

### Resume CLI

```bash
# Resume from latest checkpoint
python -m app.simulation.orchestrator --resume

# Resume from specific checkpoint
python -m app.simulation.orchestrator --resume-from ./data/checkpoints/checkpoint_2024-01-15_cycle_48.json

# Start fresh (ignore checkpoints)
python -m app.simulation.orchestrator --fresh
```

---

## Monitoring & Control

### Enhanced Dashboard

```python
# app/simulation/dashboard.py

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from dataclasses import dataclass
import statistics

@dataclass
class LatencyStats:
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    count: int = 0
    errors: int = 0


class LatencyTracker:
    """Track API latency percentiles"""

    def __init__(self, window_size: int = 1000):
        self.latencies: dict[str, list[float]] = {}
        self.errors: dict[str, int] = {}
        self.window_size = window_size

    def record(self, endpoint: str, latency_seconds: float):
        if endpoint not in self.latencies:
            self.latencies[endpoint] = []

        self.latencies[endpoint].append(latency_seconds * 1000)  # Convert to ms

        # Trim to window
        if len(self.latencies[endpoint]) > self.window_size:
            self.latencies[endpoint] = self.latencies[endpoint][-self.window_size:]

    def record_error(self, endpoint: str):
        self.errors[endpoint] = self.errors.get(endpoint, 0) + 1

    def get_stats(self, endpoint: str) -> LatencyStats:
        if endpoint not in self.latencies or not self.latencies[endpoint]:
            return LatencyStats()

        sorted_latencies = sorted(self.latencies[endpoint])
        count = len(sorted_latencies)

        return LatencyStats(
            p50=sorted_latencies[int(count * 0.50)],
            p95=sorted_latencies[int(count * 0.95)] if count >= 20 else 0,
            p99=sorted_latencies[int(count * 0.99)] if count >= 100 else 0,
            count=count,
            errors=self.errors.get(endpoint, 0),
        )

    def get_aggregate(self) -> LatencyStats:
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
            p95=sorted_latencies[int(count * 0.95)] if count >= 20 else 0,
            p99=sorted_latencies[int(count * 0.99)] if count >= 100 else 0,
            count=count,
            errors=total_errors,
        )


class SimulationDashboard:
    """Rich terminal dashboard with 5-second refresh"""

    def __init__(
        self,
        stats: 'SimulationStats',
        latency_tracker: LatencyTracker,
        memory_monitor: MemoryMonitor,
        refresh_rate: float = 5.0
    ):
        self.stats = stats
        self.latency_tracker = latency_tracker
        self.memory_monitor = memory_monitor
        self.refresh_rate = refresh_rate
        self.console = Console()
        self.paused = False
        self.status = "running"

    def build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        layout["body"].split_row(
            Layout(name="stats", ratio=2),
            Layout(name="latency", ratio=1),
        )

        return layout

    def render_stats_table(self) -> Table:
        table = Table(title="Simulation Statistics", expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Status", f"[bold]{self.status}[/bold]")
        table.add_row("Cycles Completed", str(self.stats.cycles_completed))
        table.add_row("Simulated Time", str(self.stats.simulated_datetime))
        table.add_row("Real Elapsed", f"{self.stats.elapsed_hours:.2f} hours")
        table.add_row("─" * 20, "─" * 20)
        table.add_row("Agents Active", f"{self.stats.agents_processed}/{self.stats.total_agents}")
        table.add_row("Sessions Created", str(self.stats.sessions_created))
        table.add_row("Checkouts", str(self.stats.checkouts_completed))
        table.add_row("Abandoned", str(self.stats.sessions_abandoned))
        table.add_row("─" * 20, "─" * 20)
        table.add_row("Offers Assigned", str(self.stats.offers_assigned))
        table.add_row("Events Created", str(self.stats.events_created))
        table.add_row("─" * 20, "─" * 20)
        table.add_row("Errors", f"[red]{self.stats.error_count}[/red]")
        table.add_row("Memory (MB)", f"{self.memory_monitor.get_usage_mb():.1f}")

        return table

    def render_latency_table(self) -> Table:
        table = Table(title="API Latency (ms)", expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        agg = self.latency_tracker.get_aggregate()
        table.add_row("p50", f"{agg.p50:.1f}")
        table.add_row("p95", f"{agg.p95:.1f}")
        table.add_row("p99", f"{agg.p99:.1f}")
        table.add_row("Requests", str(agg.count))
        table.add_row("Errors", f"[red]{agg.errors}[/red]")

        return table

    def render_header(self) -> Panel:
        status_color = {
            "running": "green",
            "paused": "yellow",
            "error": "red",
            "stopped": "dim",
        }.get(self.status, "white")

        return Panel(
            f"[bold {status_color}]● {self.status.upper()}[/bold {status_color}]  "
            f"[dim]Press: [bold]p[/bold]=pause  [bold]r[/bold]=resume  "
            f"[bold]c[/bold]=checkpoint  [bold]q[/bold]=quit[/dim]",
            title="Simulation Control"
        )

    def render_footer(self) -> Panel:
        return Panel(
            f"Last checkpoint: {self.stats.last_checkpoint or 'None'}  |  "
            f"Rate limit: {self.stats.current_rps:.1f} req/s",
            title="Info"
        )

    def render(self) -> Layout:
        layout = self.build_layout()
        layout["header"].update(self.render_header())
        layout["stats"].update(Panel(self.render_stats_table()))
        layout["latency"].update(Panel(self.render_latency_table()))
        layout["footer"].update(self.render_footer())
        return layout
```

### Keyboard Control Handler

```python
# app/simulation/controls.py

import sys
import asyncio
import termios
import tty
from contextlib import contextmanager

class KeyboardController:
    """Handle keyboard shortcuts for simulation control"""

    def __init__(self, orchestrator: 'SimulationOrchestrator'):
        self.orchestrator = orchestrator
        self.running = True

    @contextmanager
    def raw_mode(self):
        """Put terminal in raw mode for immediate key capture"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            yield
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    async def listen(self):
        """Listen for keyboard input"""
        loop = asyncio.get_event_loop()

        with self.raw_mode():
            while self.running:
                # Non-blocking read with timeout
                try:
                    key = await asyncio.wait_for(
                        loop.run_in_executor(None, sys.stdin.read, 1),
                        timeout=0.1
                    )
                    await self.handle_key(key)
                except asyncio.TimeoutError:
                    continue

    async def handle_key(self, key: str):
        """Handle keyboard shortcut"""
        match key.lower():
            case 'p':
                await self.orchestrator.pause()
                print("\n[PAUSED] Press 'r' to resume...")

            case 'r':
                await self.orchestrator.resume()
                print("\n[RESUMED]")

            case 'c':
                print("\n[CHECKPOINT] Saving...")
                path = await self.orchestrator.checkpoint_manager.save(
                    self.orchestrator,
                    self.orchestrator.current_cycle
                )
                print(f"[CHECKPOINT] Saved to {path}")

            case 'q':
                print("\n[QUIT] Saving checkpoint and exiting...")
                await self.orchestrator.graceful_shutdown()
                self.running = False

            case 's':
                # Print current stats
                stats = self.orchestrator.stats
                print(f"\n[STATS] Cycle {stats.cycles_completed}, "
                      f"Sessions: {stats.sessions_created}, "
                      f"Checkouts: {stats.checkouts_completed}, "
                      f"Errors: {stats.error_count}")
```

---

## Error Handling & Circuit Breaker

### Circuit Breaker Implementation

```python
# app/simulation/circuit_breaker.py

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Paused due to errors
    HALF_OPEN = "half_open"  # Testing recovery (not used in our case)


@dataclass
class CircuitBreakerConfig:
    failure_threshold_percent: float = 5.0  # 5% of agents
    window_type: str = "per_cycle"  # per_cycle or rolling_time
    auto_reset: bool = False  # Wait for manual resume


class CircuitBreaker:
    """
    Circuit breaker that pauses simulation on excessive failures.

    Triggers when >5% of agents fail in a single cycle (>18 of 372).
    Requires manual resume (freeze and wait).
    """

    def __init__(
        self,
        config: CircuitBreakerConfig,
        total_agents: int,
        on_open_callback=None
    ):
        self.config = config
        self.total_agents = total_agents
        self.on_open_callback = on_open_callback

        self.state = CircuitState.CLOSED
        self.cycle_failures = 0
        self.total_failures = 0
        self.last_failure_time = None
        self.opened_at = None

        # Calculate threshold
        self.failure_threshold = int(
            total_agents * (config.failure_threshold_percent / 100)
        )

    def record_success(self):
        """Record successful agent execution"""
        pass  # Success doesn't affect circuit breaker

    def record_failure(self, agent_id: str, error: Exception):
        """Record agent failure"""
        self.cycle_failures += 1
        self.total_failures += 1
        self.last_failure_time = datetime.now()

        # Check threshold
        if self.cycle_failures > self.failure_threshold:
            self._open_circuit()

    def reset_cycle(self):
        """Reset failure count for new cycle"""
        self.cycle_failures = 0

    def _open_circuit(self):
        """Open circuit breaker (pause simulation)"""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.now()

            if self.on_open_callback:
                asyncio.create_task(self.on_open_callback(self))

    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def manual_reset(self):
        """Manually reset circuit breaker (resume)"""
        self.state = CircuitState.CLOSED
        self.cycle_failures = 0
        self.opened_at = None

    def get_status(self) -> dict:
        return {
            "state": self.state.value,
            "cycle_failures": self.cycle_failures,
            "threshold": self.failure_threshold,
            "total_failures": self.total_failures,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }


# Usage in orchestrator:
async def on_circuit_open(circuit_breaker):
    """Callback when circuit breaker opens"""
    logger.error(
        f"CIRCUIT BREAKER OPEN: {circuit_breaker.cycle_failures} failures "
        f"exceeded threshold of {circuit_breaker.failure_threshold}"
    )
    print("\n" + "="*60)
    print("[CIRCUIT BREAKER] Simulation PAUSED due to excessive failures")
    print(f"  Failures this cycle: {circuit_breaker.cycle_failures}")
    print(f"  Threshold: {circuit_breaker.failure_threshold} (5%)")
    print("  Press 'r' to resume after investigating the issue")
    print("="*60 + "\n")
```

### Failed Checkout Handling

```python
# app/simulation/agent/actions.py

async def handle_checkout_failure(
    conn,
    agent_id: str,
    session_id: str,
    error: Exception
):
    """Handle checkout failure - clear cart, start fresh next cycle"""

    # Log the failure
    await record_event(
        conn,
        session_id=session_id,
        user_id=agent_id,
        event_type='checkout_failed',
        payload={
            'error': str(error),
            'error_type': type(error).__name__,
        }
    )

    # Clear the cart (start fresh next cycle)
    await conn.execute(
        "DELETE FROM cart_items WHERE user_id = :user_id",
        {"user_id": agent_id}
    )

    await conn.execute(
        "DELETE FROM cart_coupons WHERE user_id = :user_id",
        {"user_id": agent_id}
    )

    # Mark session as failed (not abandoned - different analytics)
    await conn.execute("""
        UPDATE shopping_sessions
        SET status = 'failed',
            ended_at = NOW(),
            notes = :error
        WHERE id = :session_id
    """, {"session_id": session_id, "error": str(error)[:500]})

    await conn.commit()
```

---

## Implementation Priority & Phases

### Phase 1: Rate Limiting (Priority 1)
**Goal**: Protect Railway API from overload

```
Tasks:
├── Implement TokenBucket rate limiter
├── Create RateLimitedAPIClient wrapper
├── Add rate limit configuration to CLI
├── Test with 50 req/s limit
└── Add rate limit metrics to dashboard

Estimated complexity: Medium
Dependencies: None
```

### Phase 2: Parallelization (Priority 2)
**Goal**: Run 372 agents concurrently

```
Tasks:
├── Convert orchestrator to async
├── Implement ParallelAgentExecutor
├── Add hybrid async model (async I/O, sync compute)
├── Implement HTTP session pooling (10 sessions)
├── Add warm-up ramp controller
├── Update database pool configuration
└── Test with increasing agent counts

Estimated complexity: High
Dependencies: Rate limiting must be in place
```

### Phase 3: Checkpoint & Resume (Priority 3)
**Goal**: Survive crashes, enable long runs

```
Tasks:
├── Implement CheckpointManager
├── Add checkpoint save on cycle completion
├── Implement orphaned session cleanup
├── Add --resume and --resume-from CLI flags
├── Add 'replay' marking for resumed runs
├── Test checkpoint/resume cycle
└── Implement checkpoint cleanup (keep last 5)

Estimated complexity: Medium
Dependencies: Basic parallelization working
```

### Phase 4: Monitoring (Priority 4)
**Goal**: Visibility into 372-agent runs

```
Tasks:
├── Implement LatencyTracker with percentiles
├── Add MemoryMonitor
├── Update Rich dashboard (5s refresh)
├── Implement KeyboardController (p/r/q/c)
├── Add circuit breaker with 5% threshold
├── Add detailed logging infrastructure
└── Create dry-run mode (--mock-api, --mock-db)

Estimated complexity: Medium
Dependencies: Core functionality working
```

---

## Configuration Reference

### CLI Arguments

```bash
python -m app.simulation.orchestrator \
    --hours 6 \                    # Real-time duration (default: 1)
    --time-scale 48 \              # Simulated hours per real hour (default: 24)
    --agents 372 \                 # Number of agents (default: all active)
    --rate-limit 50 \              # API requests per second (default: 50)
    --checkpoint-interval 10 \     # Cycles between checkpoints (default: 10)
    --warmup-cycles 10 \           # Gradual ramp-up cycles (default: 0)
    --resume \                     # Resume from latest checkpoint
    --resume-from PATH \           # Resume from specific checkpoint
    --fresh \                      # Ignore checkpoints, start fresh
    --mock-api \                   # Dry run: mock API calls
    --mock-db \                    # Dry run: mock DB writes
    --debug                        # Enable debug logging
```

### Environment Variables

```bash
# Database (Supabase)
DATABASE_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres?pgbouncer=true
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=75

# API (Railway)
RAILWAY_API_URL=https://your-app.railway.app
API_RATE_LIMIT_RPS=50

# Simulation
SIMULATION_MODE=true
TIME_SCALE=48
DEFAULT_CHECKPOINT_INTERVAL=10
CIRCUIT_BREAKER_THRESHOLD_PERCENT=5

# Monitoring
LOG_LEVEL=INFO
DASHBOARD_REFRESH_SECONDS=5
```

### Sample Configuration File

```yaml
# config/simulation.yaml
simulation:
  time_scale: 48
  rate_limit_rps: 50
  checkpoint_interval_cycles: 10
  warmup_cycles: 10

database:
  pool_size: 50
  max_overflow: 75
  pool_timeout: 30
  pool_recycle: 1800

parallelization:
  max_concurrent_agents: 372
  http_session_count: 10
  thread_pool_workers: 12

circuit_breaker:
  failure_threshold_percent: 5.0
  window_type: per_cycle
  auto_reset: false

monitoring:
  dashboard_refresh_seconds: 5
  latency_window_size: 1000
  memory_warning_mb: 12000
```

---

## Future Roadmap: 1000+ Agents

### Scaling Beyond Single Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DISTRIBUTED ARCHITECTURE (Future)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                        ┌─────────────────────┐                              │
│                        │  Coordinator Node   │                              │
│                        │  (Orchestrator)     │                              │
│                        │                     │                              │
│                        │  - Time management  │                              │
│                        │  - Work distribution│                              │
│                        │  - Result aggregation│                             │
│                        │  - Circuit breaker  │                              │
│                        └──────────┬──────────┘                              │
│                                   │                                         │
│              ┌────────────────────┼────────────────────┐                   │
│              │                    │                    │                   │
│              ▼                    ▼                    ▼                   │
│    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│    │  Worker Node 1  │  │  Worker Node 2  │  │  Worker Node N  │          │
│    │  (333 agents)   │  │  (333 agents)   │  │  (334 agents)   │          │
│    │                 │  │                 │  │                 │          │
│    │  - Agent exec   │  │  - Agent exec   │  │  - Agent exec   │          │
│    │  - Local pool   │  │  - Local pool   │  │  - Local pool   │          │
│    │  - Rate limiting│  │  - Rate limiting│  │  - Rate limiting│          │
│    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘          │
│             │                    │                    │                    │
│             └────────────────────┼────────────────────┘                    │
│                                  │                                         │
│                                  ▼                                         │
│                    ┌───────────────────────────┐                           │
│                    │   Message Queue (Redis)   │                           │
│                    │   - Work distribution     │                           │
│                    │   - Result collection     │                           │
│                    │   - Checkpoint storage    │                           │
│                    └───────────────────────────┘                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Technology Options for 1000+ Agents

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Kubernetes + Celery** | Proven, scalable | Complex setup | Production workloads |
| **Ray** | Python-native, easy scaling | Learning curve | ML-heavy workloads |
| **Dask** | Familiar API, dynamic | Less mature | Data-heavy tasks |
| **AWS Lambda** | Serverless, pay-per-use | Cold starts, 15min limit | Burst workloads |
| **Multi-process local** | Simple, no infra | Machine-limited | Up to ~500 agents |

### Recommended Path to 1000+ Agents

1. **Phase A: Optimize current approach (372→500 agents)**
   - Fine-tune connection pooling
   - Optimize memory usage
   - Consider 32GB RAM machine

2. **Phase B: Multi-process local (500→1000 agents)**
   - Split agents across processes
   - Shared Redis for coordination
   - Single machine, multiple cores

3. **Phase C: Distributed workers (1000+ agents)**
   - Kubernetes deployment
   - Celery/Redis for work distribution
   - Horizontal scaling

### Database Scaling for High Volume

```
Current: Supabase Pro (100 connections)
    │
    ▼
Option 1: Supabase Team (500 connections)
    │
    ▼
Option 2: Self-hosted PostgreSQL + PgBouncer
    │
    ▼
Option 3: Read replicas for analytics queries
    │
    ▼
Option 4: Event streaming (Kafka) for writes, batch DB inserts
```

---

## Appendix: Quick Start Commands

```bash
# Test with 10 agents (current working setup)
python -m app.simulation.orchestrator --hours 1 --time-scale 96 --agents 10

# Test rate limiting with 50 agents
python -m app.simulation.orchestrator --hours 1 --time-scale 48 --agents 50 --rate-limit 50

# Dry run 372 agents (no API/DB)
python -m app.simulation.orchestrator --hours 1 --time-scale 48 --agents 372 --mock-api --mock-db

# Production run with checkpointing
python -m app.simulation.orchestrator --hours 6 --time-scale 48 --checkpoint-interval 10 --warmup-cycles 10

# Resume from crash
python -m app.simulation.orchestrator --resume
```

---

*Document generated: 2024-01-15*
*Target: 372 agent simulation scaling*
*Author: Claude Code*
