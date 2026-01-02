# Scaling Plan for 372-Agent Simulation

**Date:** January 2, 2026  
**Target:** Execute 372 agents simultaneously  
**Hardware:** M1 Pro MacBook Pro (16GB RAM, 8 CPU cores)  
**Database:** Supabase Pro ($25/month, remote PostgreSQL)  

---

## Executive Summary

The current simulation engine has been tested with 2 agents and 10 agents successfully. This plan outlines the architecture and configuration changes required to scale to **372 concurrent agents**. The scaling strategy focuses on:

1. **Database Connection Pooling** - Optimize for high-concurrency writes
2. **API Rate Limiting** - Handle bulk API calls to cart/checkout endpoints
3. **Resource Management** - Multi-threading and memory optimization for M1 Pro
4. **Monitoring & Checkpointing** - Real-time visibility and resumability
5. **Error Handling** - Graceful degradation and recovery mechanisms

---

## Architecture Overview

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Simulation Orchestrator (Single Process)     │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │  Agent 1 │  Agent 2 │  Agent 3 │  ...     │          │
│  └────┬─────┴────┬─────┴────┬─────┴──────────┘          │
└───────┼───────────┼───────────┼───────────────────────────┘
        │           │           │                           
        ▼           ▼           ▼                           
┌─────────────────────────────────────────────────────────────┐
│         Shopping Graph (LangGraph Sequential)               │
│  decide_shop → browse → add_cart → coupons → checkout       │
└─────────────────────────────────────────────────────────────┘
        │           │           │
        ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│              Database (Supabase Remote)                    │
│         Connection Pool: 5 base, +10 overflow             │
└─────────────────────────────────────────────────────────────┘
```

### Bottlenecks at 372 Agents

| Component | Current Limit | Expected Load | Bottleneck Severity |
|-----------|--------------|----------------|-------------------|
| DB Pool | 5 base + 10 overflow (15 total) | 372 × ~6 writes/agent | **CRITICAL** |
| Agent Execution | Sequential in orchestrator loop | 372 concurrent | **HIGH** |
| Shopping Graph | 1 agent at a time | 372 concurrent requests | **HIGH** |
| LLM API Calls | 1 concurrent request | Generation: 372 personas | **MEDIUM** |
| Memory | ~200MB for 10 agents | ~7.4GB for 372 agents | **MEDIUM** |
| CPU | 8 cores (mostly idle) | 372 threads | **LOW** |

---

## 1. Database Connection Pooling Strategy

### Problem Statement

**Current Configuration:**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,           # Base connections
    max_overflow=10,        # Additional when pool full
    pool_pre_ping=True,     # Health check
    pool_recycle=3600      # Recycle after 1 hour
)
```

**Analysis:**
- Each agent performs ~6 database operations per shopping session:
  1. `touch_shopping_session()` - 1 write
  2. `create_session()` - 1 write
  3. `browse_products()` - 1 read + 5 writes (events)
  4. `add_to_cart()` - 1 write (upsert)
  5. `view_coupons()` - 1 read + 1 write (event)
  6. `complete_checkout()` - ~10 writes (order, order_items, coupons, interactions)
  7. `record_shopping_event()` - 1 write per action

- **Total writes per agent:** ~20-30 writes/minute (including shopping_session_events)
- **Total concurrent writes at 372 agents:** ~7,440 - 11,160 writes/minute

**Supabase Pro Limits:**
- Max concurrent connections: 60 (per official documentation)
- Connection establishment time: 100-200ms (remote)
- Query execution time: 50-150ms (indexed queries)
- **Total transaction time per write:** ~200-350ms

**Calculate Required Connections:**
```
writes_per_minute = 372 agents × 25 writes/agent = 9,300 writes/min
throughput_per_connection = (60,000ms / 300ms) = 200 writes/min/conn
connections_needed = 9,300 / 200 = 46.5 connections

Add 20% buffer for variance and connection churn:
connections_needed = 46.5 × 1.2 = 56 connections
```

### Solution 1: Increase Connection Pool (RECOMMENDED)

**Configuration Changes:**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=50,            # Increase from 5 to 50
    max_overflow=10,         # Keep buffer
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,          # Wait up to 30s for connection
    pool_use_lifo=True,       # Use most recent connection (better cache locality)
    echo=False,               # Disable SQL logging in production
)
```

**Benefits:**
- Covers 56 connections with 50 base + 10 overflow = 60 connections (matches Supabase limit)
- `pool_use_lifo=True` reduces context switching overhead
- Maintains 20% buffer for spikes

**Trade-offs:**
- Higher memory usage: ~1-2MB per connection = ~60-120MB total (acceptable)
- Potential connection exhaustion if >60 concurrent operations
- Slower pool initialization on startup

### Solution 2: Use Connection Pool with Queue (ALTERNATIVE)

If hitting Supabase limit frequently:

```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=40,
    max_overflow=20,        # Allow temporary spike
    pool_timeout=30,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

**Benefits:**
- Queues requests when pool is full instead of failing
- Handles burst traffic better
- Can exceed Supabase limit temporarily (graceful degradation)

**Trade-offs:**
- Request queuing increases latency
- Risk of timeout (30s) if pool starved
- More complex debugging

### Solution 3: Batch Database Writes (OPTIMIZATION)

Reduce write frequency by batching shopping_session_events:

```python
# In orchestrator.py - batch events before commit
class EventBatcher:
    def __init__(self, db: Session, batch_size: int = 50):
        self.db = db
        self.batch_size = batch_size
        self.pending_events = []
    
    def add_event(self, event: dict):
        self.pending_events.append(event)
        if len(self.pending_events) >= self.batch_size:
            self.flush()
    
    def flush(self):
        if not self.pending_events:
            return
        
        # Bulk insert using executemany()
        self.db.execute(
            text("""
                INSERT INTO shopping_session_events (id, session_id, user_id, event_type, payload, created_at)
                VALUES :events
            """),
            {"events": self.pending_events}
        )
        self.pending_events = []
```

**Benefits:**
- Reduces write count from ~25 to ~8 writes/agent (batch events)
- 3x reduction in connection usage
- Faster commit times

**Trade-offs:**
- Events not immediately visible (acceptable for simulation)
- Risk of event loss if process crashes mid-batch
- Need to flush on agent completion

### **RECOMMENDATION: Solution 1 (Configure Connection Pool)**
- Update `orchestrator.py` to create engine with proper pool settings
- Set `pool_size=50`, `max_overflow=10` (60 total connections)
- Add `pool_use_lifo=True` for warm connection reuse
- Add `pool_pre_ping=True` for health checks
- Add `pool_timeout=30` to queue requests when pool full

---

## 2. API Call Rate Limiting Strategy

### Problem Statement

The simulation engine makes API calls to:
1. **Internal backend endpoints** (running on Railway/localhost)
2. **LLM API** (OpenRouter for persona generation)
3. **External services** (optional, not used currently)

**Backend API Endpoints Called:**
```
POST /api/cart/items           - Add to cart
POST /api/cart/coupons        - Apply coupon
POST /api/orders               - Checkout
GET  /api/products/search      - Browse products
GET  /api/coupons/eligible    - View coupons
GET  /api/coupons/wallet      - Get user coupons
POST /api/shopping/session     - Create session
```

**Current Rate Limits (from main.py):**
```python
limiter = Limiter(key_func=get_remote_address)
limiter.limit("10/minute")(stt_endpoint)
limiter.limit("30/minute")(search_endpoints)
limiter.limit("60/minute")(product_endpoints)
```

**Analysis:**
- **10 agents:** 10 × 6 calls/agent = 60 calls/min (within limits)
- **372 agents:** 372 × 6 calls/agent = 2,232 calls/min (20x over limit)
- **Peak rate:** 372 agents × 3 calls/checkout × 10 min = 11,160 calls in 10 min

### Solution 1: Use Existing SIMULATION_MODE Bypass (RECOMMENDED)

**Implementation (Already in main.py lines 284-298):**

```python
# From app/main.py
# SIMULATION MODE BYPASS (B-8)
if os.getenv("SIMULATION_MODE", "false").lower() == "true":
    # Accept "Bearer dev:<agent_id>" format instead of JWT
    if authorization.startswith("Bearer dev:"):
        agent_id = authorization.replace("Bearer dev:", "").strip()
        return {
            "user_id": f"{agent_id}@simulation.local",
            "email": f"{agent_id}@simulation.local",
            "is_simulation": True,
        }
```

**Usage in orchestrator:**
```bash
# Set SIMULATION_MODE=true before running
export SIMULATION_MODE=true

# The orchestrator automatically uses Authorization: "Bearer dev:agent_001"
# which is accepted by main.py verify_token() without JWT generation
SIMULATION_MODE=true python -m app.simulation.orchestrator --hours 6
```

**Pros:**
- ✅ Already implemented and tested (10-agent simulation)
- ✅ No JWT generation overhead
- ✅ Simple Authorization format
- ✅ No code changes needed
- ✅ Zero API latency for token generation

**Cons:**
- ⚠️ Requires SIMULATION_MODE=true environment variable
- ⚠️ Dev token format (not production-ready)
- ⚠️ No audit trail for individual agents

**RECOMMENDATION:** Use existing SIMULATION_MODE bypass. Set environment variable before running simulation. No implementation needed.

**Benefits:**
- Simple to implement
- Zero code changes to rate limiting logic
- Only bypasses when header present

**Trade-offs:**
- Risk of accidental production bypass if header leaked
- Need to ensure JWT tokens are generated correctly

### Solution 2: Use Bulk API Endpoints (ALTERNATIVE)

Create new bulk endpoints specifically for simulation:

```python
# In routes/simulation.py (new file)
@router.post("/api/simulation/bulk-cart-add")
async def bulk_add_to_cart(request: BulkCartAddRequest):
    """Add multiple items to carts in batch."""
    
    # Batch insert all items
    items = request.items  # List of (user_id, store_id, product_id, quantity)
    db.execute(
        text("""
            INSERT INTO cart_items (user_id, store_id, product_id, quantity)
            VALUES :items
            ON CONFLICT (user_id, store_id, product_id)
            DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        """),
        {"items": items}
    )
    db.commit()
    return {"success": True, "processed": len(items)}
```

**Benefits:**
- Single API call for multiple operations
- Reduces HTTP overhead
- Better for bulk processing

**Trade-offs:**
- Requires new endpoints
- More complex error handling
- Doesn't help with checkout (still needs per-agent logic)

### Solution 3: Connection Pooling for HTTP Client (OPTIMIZATION)

Reuse HTTP connections instead of creating new ones:

```python
# In orchestrator.py
import httpx

class SimulationAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=100,    # Keep 100 connections open
                max_connections=200,             # Max concurrent connections
                keepalive_expiry=30.0            # Close after 30s idle
            ),
            timeout=httpx.Timeout(10.0)         # 10s timeout
        )
    
    async def add_to_cart(self, user_id: str, payload: dict):
        response = await self.client.post(
            f"{self.base_url}/api/cart/items",
            json=payload,
            headers={"Authorization": f"Bearer {self.get_jwt(user_id)}", "X-Simulation-Mode": "true"}
        )
        return response.json()
```

**Benefits:**
- Reuses TCP connections (saves ~50ms per request on connection setup)
- Handles 372 concurrent requests efficiently
- Built-in rate limiting and connection pooling

**Trade-offs:**
- More complex initialization
- Need to handle connection failures gracefully

### **RECOMMENDATION: Solution 1 (Exempt Simulation) + Solution 3 (HTTP Pooling)**
- Add `X-Simulation-Mode: true` header to bypass rate limits
- Use `httpx.AsyncClient` with connection pooling
- Set max_keepalive_connections=100, max_connections=200

---

## 3. Multi-Threading & Resource Management

### Problem Statement

**Current Execution Model:**
```python
# From orchestrator.py - _run_cycle()
async def _run_cycle(self, agents: List[Dict[str, Any]]):
    # Process each agent sequentially
    for agent in agents:
        self.stats.agents_processed += 1
        result = await self._run_agent(agent, sim_date)  # BLOCKING
        ...
```

**Analysis:**
- **Current:** Sequential execution = 372 × ~2s per agent = 744 seconds (12.4 minutes) per cycle
- **Target:** Concurrent execution = 372 × ~2s / 50 = ~15 seconds per cycle
- **Improvement:** 50x faster (12.4 minutes → 15 seconds per cycle)
- Each agent runs LangGraph shopping_graph (synchronous invoke)
- **Current:** Only 1 CPU core utilized at a time (others idle)
- **Target:** Utilize all 8 cores via asyncio
- M1 Pro: 8 cores (4 performance, 4 efficiency) mostly idle currently

**Memory Footprint:**
- **Per agent state:** ~50KB (AgentState + products_data + cart_items)
- **Per agent graph:** ~100KB (LangGraph compiled graph)
- **Total for 372 agents:** (50KB + 100KB) × 372 = ~56MB (negligible)
- **With 50 concurrent agents:** 50 × 150KB = 7.5MB in flight
- **Database connections:** 60 × 1MB = ~60MB (with proper pooling)
- **Python overhead:** ~500MB (runtime, objects, GC)
- **Total estimated memory:** ~600-800MB (well within 16GB)

### Solution 1: asyncio.gather() with Semaphore (RECOMMENDED - TO BE IMPLEMENTED)

**Replace sequential _run_cycle() with concurrent version:**

```python
async def _run_cycle_concurrent(self, agents: List[Dict[str, Any]], max_concurrent: int = 50):
    """
    Execute agents concurrently with limited concurrency.
    
    Args:
        agents: List of agent dictionaries
        max_concurrent: Max agents to run simultaneously (default 50)
    """
    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_agent_with_semaphore(agent: Dict[str, Any]):
        """Run single agent with semaphore."""
        async with semaphore:
            return await self._run_agent(agent, self.stats.simulated_datetime.date())
    
    # Execute all agents concurrently (up to max_concurrent at once)
    tasks = [run_agent_with_semaphore(agent) for agent in agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for agent, result in zip(agents, results):
        self.stats.agents_processed += 1
        
        if isinstance(result, Exception):
            logger.error(f"Agent {agent_id} failed: {result}")
            self.stats.errors += 1
        elif result.get("should_shop"):
            self.stats.agents_shopped += 1
            self.stats.sessions_created += 1
            self.stats.events_created += result.get("events_created", 0)
            
            if result.get("checkout_decision") == "complete":
                self.stats.checkouts_completed += 1
            elif result.get("checkout_decision") == "abandon":
                self.stats.checkouts_abandoned += 1
    
    # Commit all changes at once
    self.db.commit()
```

**Integration with CLI:**
```python
# In orchestrator.py __main__ (line 712)
parser.add_argument(
    "--max-concurrent",
    type=int,
    default=50,
    help="Max concurrent agents (default: 50)"
)
```

**Usage:**
```bash
python -m app.simulation.orchestrator \
    --hours 6 \
    --max-concurrent 50 \
    --process-all-agents
```

**Benefits:**
- Utilizes all CPU cores (8 cores × concurrency)
- Reduces cycle time from 12.4 minutes to ~30 seconds (50 concurrent)
- Simple to implement with asyncio
- Graceful error handling with return_exceptions=True

**Trade-offs:**
- Increased memory pressure (50 agents in flight vs 1)
- Complex debugging with concurrent operations
- Need to handle database transaction conflicts

### Solution 2: Process Pool with multiprocessing (ALTERNATIVE)

Use multiprocessing for CPU-bound operations (if any):

```python
from concurrent.futures import ProcessPoolExecutor

class SimulationOrchestrator:
    def __init__(self, ..., use_multiprocessing: bool = False):
        self.use_multiprocessing = use_multiprocessing
        if use_multiprocessing:
            self.executor = ProcessPoolExecutor(max_workers=8)  # 8 CPU cores
```

**Benefits:**
- True parallelism (bypasses GIL)
- Better for CPU-intensive workloads
- Isolated processes (one agent crash doesn't affect others)

**Trade-offs:**
- High overhead (process spawning, serialization)
- Doesn't help with I/O-bound operations (database, network)
- More complex state management

### Solution 3: Adaptive Concurrency (OPTIMIZATION)

Dynamically adjust concurrency based on system load:

```python
import psutil  # pip install psutil

class AdaptiveConcurrencyManager:
    def __init__(self, base_concurrency: int = 50):
        self.base_concurrency = base_concurrency
        self.max_concurrency = 100
        self.min_concurrency = 20
    
    def get_concurrency(self) -> int:
        """Get current concurrency based on system load."""
        # Get CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem_percent = psutil.virtual_memory().percent
        
        # Reduce concurrency if high load
        if cpu_percent > 80 or mem_percent > 80:
            return max(self.min_concurrency, self.base_concurrency // 2)
        
        # Increase concurrency if low load
        if cpu_percent < 50 and mem_percent < 50:
            return min(self.max_concurrency, self.base_concurrency * 2)
        
        return self.base_concurrency
```

**Benefits:**
- Prevents system overload
- Maximizes throughput under good conditions
- Automatic adaptation to changing load

**Trade-offs:**
- Additional dependency (psutil)
- Complex tuning of thresholds
- May oscillate under varying conditions

### **RECOMMENDATION: Solution 1 (asyncio.gather) with Solution 3 (Adaptive Concurrency)**
- Use asyncio.Semaphore(50) for base concurrency
- Implement adaptive concurrency based on CPU/memory
- Monitor and log concurrency adjustments
- Start with 50, scale up to 100 if resources available

---

## 4. Monitoring & Real-Time Dashboard

### Problem Statement

**Current Dashboard:**
```python
# From orchestrator.py - _build_simple_dashboard()
table.add_row("Agents Processed", str(self.stats.agents_processed))
table.add_row("Agents Shopped", str(self.stats.agents_shopped))
table.add_row("Sessions Created", str(self.stats.sessions_created))
```

**Limitations at 372 Agents:**
- No visibility into per-agent progress (which agents are stuck?)
- No error tracking beyond count
- No performance metrics (latency, throughput)
- No resource utilization monitoring
- Dashboard updates once per cycle (too slow for real-time)

### Solution 1: Enhanced Rich Dashboard (RECOMMENDED)

```python
@dataclass
class DetailedSimulationStats:
    """Enhanced statistics with per-agent tracking."""
    start_time: float = field(default_factory=time.time)
    simulated_datetime: Optional[datetime] = None
    cycles_completed: int = 0
    agents_processed: int = 0
    agents_shopped: int = 0
    agents_failed: int = 0
    
    # Performance metrics
    avg_agent_latency_ms: float = 0.0
    p95_agent_latency_ms: float = 0.0
    p99_agent_latency_ms: float = 0.0
    writes_per_second: float = 0.0
    api_calls_per_second: float = 0.0
    
    # Resource metrics
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    active_db_connections: int = 0
    
    # Error tracking
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    failed_agent_ids: List[str] = field(default_factory=list)
    
    # Progress tracking
    current_batch: int = 0
    total_batches: int = 0
    percent_complete: float = 0.0

class SimulationOrchestrator:
    def __build_enhanced_dashboard(self) -> Panel:
        """Build enhanced dashboard with multiple sections."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=5),
        )
        
        layout["main"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="progress", ratio=1),
            Layout(name="errors", ratio=1),
        )
        
        # Header section
        header_text = (
            f"[bold blue]VoiceOffers Simulation[/bold blue] | "
            f"Agents: {self.stats.agents_processed}/{self.total_agents} | "
            f"Time: {self.stats.simulated_datetime or 'N/A'}"
        )
        layout["header"].update(Panel(header_text, style="on blue"))
        
        # Stats table
        stats_table = Table(title="Performance Metrics", show_header=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Cycle Time", f"{self.stats.avg_cycle_time:.2f}s")
        stats_table.add_row("Avg Agent Latency", f"{self.stats.avg_agent_latency_ms:.0f}ms")
        stats_table.add_row("Writes/sec", f"{self.stats.writes_per_second:.0f}")
        stats_table.add_row("CPU", f"{self.stats.cpu_percent:.0f}%")
        stats_table.add_row("Memory", f"{self.stats.memory_mb:.0f}MB")
        stats_table.add_row("DB Connections", f"{self.stats.active_db_connections}")
        
        layout["stats"].update(Panel(stats_table, title="[bold]Stats[/bold]"))
        
        # Progress bar
        progress_bar = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        )
        progress_bar.add_task("Agents", completed=self.stats.agents_processed, total=self.total_agents)
        layout["progress"].update(Panel(progress_bar, title="[bold]Progress[/bold]"))
        
        # Errors table
        errors_table = Table(title="Errors", show_header=True)
        errors_table.add_column("Error Type", style="red")
        errors_table.add_column("Count", style="yellow")
        errors_table.add_column("Last Agent", style="dim")
        
        for error_type, count in self.stats.errors_by_type.items():
            last_agent = self.stats.failed_agent_ids[-1] if self.stats.failed_agent_ids else "N/A"
            errors_table.add_row(error_type, str(count), last_agent[:10])
        
        layout["errors"].update(Panel(errors_table, title="[bold]Errors[/bold]"))
        
        # Footer with recent errors
        if self.stats.last_errors:
            recent_errors = "\n".join(self.stats.last_errors[-3:])
            layout["footer"].update(
                Panel(recent_errors, title="[bold red]Recent Errors[/bold red]", border_style="red")
            )
        
        return Panel(layout)
```

**Benefits:**
- Real-time visibility into all aspects
- Performance metrics for optimization
- Error tracking and debugging aid
- Progress bar for ETA

**Trade-offs:**
- More complex dashboard code
- Slightly higher CPU usage for rendering
- Terminal width requirements (need 120+ columns)

### Solution 2: CSV/JSON Logging for External Monitoring (OPTIMIZATION)

Export metrics to file for external tools (Grafana, Datadog):

```python
class MetricsExporter:
    def __init__(self, output_path: str = "simulation_metrics.csv"):
        self.output_path = output_path
        self.file = open(output_path, "w")
        self.csv_writer = csv.writer(self.file)
        self.csv_writer.writerow([
            "timestamp", "cycle", "agents_processed", "agents_shopped",
            "avg_latency_ms", "writes_per_sec", "cpu_percent", "memory_mb"
        ])
    
    def export_metrics(self, stats: DetailedSimulationStats):
        """Export metrics to CSV."""
        self.csv_writer.writerow([
            datetime.now().isoformat(),
            stats.cycles_completed,
            stats.agents_processed,
            stats.agents_shopped,
            stats.avg_agent_latency_ms,
            stats.writes_per_second,
            stats.cpu_percent,
            stats.memory_mb,
        ])
        self.file.flush()
```

**Benefits:**
- External monitoring tool integration
- Post-simulation analysis
- Historical comparison

**Trade-offs:**
- Additional I/O overhead
- Need to manage file rotation

### **RECOMMENDATION: Solution 1 (Enhanced Dashboard) + Solution 2 (CSV Logging)**
- Implement enhanced Rich dashboard with 3-column layout
- Add progress bar, performance metrics, error tracking
- Export metrics to CSV every cycle for external analysis

---

## 5. Checkpointing & Resumability

### Problem Statement

**Current Behavior:**
- Simulation runs continuously for `duration_hours`
- No intermediate saves
- If process crashes (OOM, network error), all progress lost
- Must restart from beginning

**Failure Scenarios:**
1. **Out of Memory:** If 372 agents exceed 16GB RAM
2. **Network Error:** Supabase connection timeout
3. **Process Killed:** SIGTERM/SIGINT (Ctrl+C) loses state
4. **Python Crash:** Unhandled exception in agent logic
5. **LLM API Error:** If generating personas during simulation

### Solution 1: Time-Based Checkpointing (RECOMMENDED)

```python
@dataclass
class SimulationCheckpoint:
    """Checkpoint data structure."""
    timestamp: float
    cycle: int
    agents_completed: List[str]  # IDs of completed agents
    agents_in_progress: List[str]  # IDs currently being processed
    stats: DetailedSimulationStats
    simulated_datetime: Optional[datetime] = None

class CheckpointManager:
    def __init__(self, checkpoint_interval_seconds: int = 300):
        """
        Args:
            checkpoint_interval_seconds: Save checkpoint every N seconds (default: 5 min)
        """
        self.checkpoint_interval_seconds = checkpoint_interval_seconds
        self.last_checkpoint_time: float = 0
        self.checkpoint_path: Path = Path("data/checkpoints")
        self.checkpoint_path.mkdir(parents=True, exist_ok=True)
    
    def should_checkpoint(self, current_time: float) -> bool:
        """Check if checkpoint should be created."""
        elapsed = current_time - self.last_checkpoint_time
        return elapsed >= self.checkpoint_interval_seconds
    
    def save_checkpoint(self, checkpoint: SimulationCheckpoint):
        """Save checkpoint to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_file = self.checkpoint_path / f"checkpoint_{timestamp}.json"
        
        with open(checkpoint_file, "w") as f:
            json.dump(asdict(checkpoint), f, indent=2)
        
        # Keep only latest 10 checkpoints
        self._cleanup_old_checkpoints()
    
    def load_latest_checkpoint(self) -> Optional[SimulationCheckpoint]:
        """Load most recent checkpoint."""
        checkpoints = sorted(self.checkpoint_path.glob("checkpoint_*.json"))
        if not checkpoints:
            return None
        
        latest = checkpoints[-1]
        with open(latest, "r") as f:
            data = json.load(f)
        
        return SimulationCheckpoint(**data)
    
    def _cleanup_old_checkpoints(self, keep: int = 10):
        """Delete old checkpoints, keeping N most recent."""
        checkpoints = sorted(self.checkpoint_path.glob("checkpoint_*.json"))
        for old_checkpoint in checkpoints[:-keep]:
            old_checkpoint.unlink()
```

**Integration with Orchestrator:**

```python
async def _run_loop(self, agents: List[Dict[str, Any]], target_end_time: float, ...):
    """Main simulation loop with checkpointing."""
    checkpoint_manager = CheckpointManager(checkpoint_interval_seconds=300)  # 5 min
    
    # Check for existing checkpoint
    if checkpoint := checkpoint_manager.load_latest_checkpoint():
        self.console.print(f"[yellow]Resuming from checkpoint at cycle {checkpoint.cycle}[/yellow]")
        self.stats = checkpoint.stats
        # Resume agents from checkpoint state...
    
    while time.time() < target_end_time and not self._stop_requested:
        current_time = time.time()
        
        try:
            # Run cycle
            await self._run_cycle_concurrent(agents)
            
            # Checkpoint if needed
            if checkpoint_manager.should_checkpoint(current_time):
                checkpoint = SimulationCheckpoint(
                    timestamp=current_time,
                    cycle=self.stats.cycles_completed,
                    agents_completed=[a['agent_id'] for a in agents if a['completed']],
                    agents_in_progress=[a['agent_id'] for a in agents if not a['completed']],
                    stats=self.stats,
                    simulated_datetime=self.stats.simulated_datetime,
                )
                checkpoint_manager.save_checkpoint(checkpoint)
                self.console.print(
                    f"[green]Checkpoint saved at cycle {self.stats.cycles_completed}[/green]"
                )
        
        except Exception as e:
            # Save emergency checkpoint before crashing
            checkpoint = SimulationCheckpoint(
                timestamp=time.time(),
                cycle=self.stats.cycles_completed,
                agents_completed=[],
                agents_in_progress=[],
                stats=self.stats,
                simulated_datetime=self.stats.simulated_datetime,
            )
            checkpoint_manager.save_checkpoint(checkpoint)
            self.console.print(f"[red]Emergency checkpoint saved[/red]")
            raise
```

**Benefits:**
- Automatic recovery from failures
- Only 5 minutes of work lost per crash
- Can resume from any checkpoint
- Emergency checkpoint on crash

**Trade-offs:**
- ~1MB per checkpoint (372 agents × 3KB)
- Slight I/O overhead every 5 minutes
- Complex state restoration logic

### Solution 2: Database-Backed Checkpointing (ALTERNATIVE)

Store checkpoints in database for distributed scenarios:

```python
CREATE TABLE simulation_checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_time TIMESTAMP NOT NULL,
    cycle_number INTEGER NOT NULL,
    stats_data JSONB NOT NULL,
    agent_state JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulation_checkpoints_cycle ON simulation_checkpoints(cycle_number);
```

**Benefits:**
- Accessible from multiple machines
- Queryable (e.g., "restore from cycle 50")
- No file system dependencies

**Trade-offs:**
- Slower than file-based (network I/O)
- Database write overhead
- Need cleanup job for old checkpoints

### **RECOMMENDATION: Solution 1 (File-Based Checkpointing)**
- Save checkpoints every 5 minutes (configurable)
- Keep 10 most recent checkpoints
- Emergency checkpoint on crash
- Simple JSON format for easy inspection

---

## 6. LLM API Rate Limiting Strategy

**Status:** NOT APPLICABLE - Personas Already Generated

### Problem Statement (Historical)

**Note:** This section was planned for persona generation via LLM API calls. However, all 372 agent personas have already been pre-generated and seeded into the database via `seed_simulation_agents.py`.

**Current State:**
- **Persona Source:** `agents` table in database
- **Seeding Script:** `scripts/seed_simulation_agents.py`
- **Seeding Date:** Already completed (372 agents)
- **LLM Calls:** Zero - personas loaded from database, not generated via API
- **Implementation:** `app/simulation/orchestrator.py` loads agents via `_load_agents()` method (line 446-483)

### Actions Required

**NONE** - No LLM API calls needed for current simulation run.

**Future Considerations:**

If personas need to be regenerated (e.g., schema changes, additional diversity):
1. Use existing `seed_simulation_agents.py` script with new Excel/JSON data
2. Regenerate via `app/simulation/cli.py generate` command (uses LLM API)
3. At that time, consider adaptive rate limiting from original design
4. Current simulation requires no LLM changes

**Benefits of Pre-Generated Personas:**
- ✅ Zero LLM latency
- ✅ No API costs
- ✅ No rate limiting concerns
- ✅ Instant agent loading from database
- ✅ Predictable simulation behavior

**Trade-offs:**
- ⚠️ Requires manual regeneration if schema changes
- ⚠️ Not flexible for real-time persona customization

---

## 7. Complete Implementation Plan

### Phase 1: Infrastructure Changes (1 day)

**Tasks:**
1. Update database connection pool in `app/simulation/orchestrator.py`
2. Add asyncio.gather() concurrent execution to `_run_cycle()`
3. Add CLI option `--max-concurrent` for concurrency control
4. Implement adaptive concurrency manager class
5. Add checkpoint manager class (TODO - see Phase 3)
6. Remove LLM persona generation tasks (already done)

**Commands:**
```bash
# 1. Edit app/simulation/orchestrator.py
# Update engine configuration (line 667)
# Configure: pool_size=50, max_overflow=10, pool_use_lifo=True, pool_pre_ping=True

# 2. Edit app/simulation/orchestrator.py
# Replace _run_cycle() with _run_cycle_concurrent()
# Add asyncio.gather() with semaphore
# Add AdaptiveConcurrencyManager class

# 3. Edit app/simulation/orchestrator.py
# Add --max-concurrent CLI argument (line 712)
# Default to 50, range 20-100
```

### Phase 2: Concurrency & Monitoring (1 day)

**Tasks:**
1. Refactor orchestrator to use asyncio.gather()
2. Implement adaptive concurrency
3. Build enhanced Rich dashboard
4. Add CSV metrics export

**Commands:**
```bash
# 1. Edit app/simulation/orchestrator.py
# Replace sequential loop with asyncio.gather()
# Add semaphore for concurrency control

# 2. Create app/simulation/concurrency_manager.py
# Implement AdaptiveConcurrencyManager with psutil

# 3. Edit app/simulation/orchestrator.py
# Update _build_dashboard() with enhanced layout
# Add performance metrics tracking

# 4. Create app/simulation/metrics_exporter.py
# Implement CSV metrics export every cycle
```

### Phase 3: Checkpointing & Error Handling (1 day)

**Tasks:**
1. Implement file-based checkpointing
2. Add emergency checkpoint on crash
3. Add comprehensive error logging
4. **Remove LLM rate limiting** (not needed - personas pre-generated)

**Commands:**
```bash
# 1. Create app/simulation/checkpoint_manager.py
# Implement CheckpointManager class
# Save to JSON files every 5 minutes
# Keep 10 most recent checkpoints

# 2. Edit app/simulation/orchestrator.py
# Integrate CheckpointManager into _run_loop()
# Add --checkpoint-interval CLI option
# Add resume-from-checkpoint logic

# 3. Create app/simulation/error_handler.py
# Implement error classification (transient/permanent)
# Add comprehensive error logging to file
```

### Phase 4: Testing & Validation (2 days)

**Test Progression (Simplified - Start at Medium Scale):**
1. **50 agents** - Validate core functionality, DB pool, basic concurrency
2. **100 agents** - Verify resource usage, adaptive concurrency, checkpointing
3. **250 agents** - Stress test, identify bottlenecks
4. **372 agents** - Full scale production run

**Commands:**
```bash
# Test 1: Medium scale (50 agents) - START HERE
SIMULATION_MODE=true python -m app.simulation.orchestrator \
    --hours 0.5 \
    --time-scale 24 \
    --max-concurrent 50 \
    --process-all-agents \
    --log-file test_50_agents.log

# Test 2: Large scale (100 agents)
SIMULATION_MODE=true python -m app.simulation.orchestrator \
    --hours 1 \
    --time-scale 24 \
    --max-concurrent 80 \
    --process-all-agents \
    --log-file test_100_agents.log

# Test 3: Extended scale (250 agents)
SIMULATION_MODE=true python -m app.simulation.orchestrator \
    --hours 2 \
    --time-scale 24 \
    --max-concurrent 100 \
    --process-all-agents \
    --log-file test_250_agents.log

# Test 4: Full scale (372 agents)
SIMULATION_MODE=true python -m app.simulation.orchestrator \
    --hours 6 \
    --time-scale 24 \
    --max-concurrent 50 \
    --process-all-agents \
    --log-file full_372_agents.log
```

**Note:** Skip 2-agent and 10-agent smoke tests - already validated in previous runs. Start directly at 50 agents.

### Phase 5: Documentation & Deployment (1 day)

**Tasks:**
1. Update README with scaling instructions
2. Create monitoring dashboard guide
3. Document checkpoint recovery process
4. Set up Supabase connection monitoring

**Commands:**
```bash
# Create docs/monitoring-guide.md
# Explain dashboard metrics and troubleshooting

# Update README.md
# Add "Running Large-Scale Simulations" section

# Create docs/checkpoint-recovery.md
# Step-by-step recovery guide
```

---

## 8. Configuration Reference

### Recommended Configuration for 372 Agents

```python
# app/main.py - Database Pool
engine = create_engine(
    DATABASE_URL,
    pool_size=50,              # Increased from 5
    max_overflow=10,           # Keep buffer
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    pool_use_lifo=True,        # New
    echo=False,
)

# app/simulation/orchestrator.py - Concurrency
DEFAULT_MAX_CONCURRENT = 50    # Start with 50
ADAPTIVE_ENABLED = True          # Enable adaptive
CPU_THRESHOLD_HIGH = 80          # Reduce concurrency at 80% CPU
CPU_THRESHOLD_LOW = 50          # Increase concurrency below 50%

# app/simulation/orchestrator.py - Checkpointing
CHECKPOINT_INTERVAL_SECONDS = 300   # 5 minutes
CHECKPOINT_KEEP_COUNT = 10           # Keep 10 checkpoints

# app/simulation/cli.py - CLI Defaults
@click.option("--max-concurrent", default=50, help="Max concurrent agents")
@click.option("--checkpoint-interval", default=300, help="Checkpoint interval (seconds)")
@click.option("--adaptive", is_flag=True, default=True, help="Enable adaptive concurrency")
```

### Environment Variables

```bash
# .env
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
SIMULATION_MODE=true              # Enable simulation mode
LANGCHAIN_TRACING_V2=true         # Enable LangSmith tracing (optional)
SIMULATION_MAX_CONCURRENT=50       # Override default concurrency
SIMULATION_CHECKPOINT_INTERVAL=300  # Override checkpoint interval
```

---

## 9. Monitoring Dashboard Guide

### Key Metrics to Watch

| Metric | Healthy | Warning | Critical | Action |
|---------|----------|----------|----------|---------|
| **Cycle Time** | < 60s | 60-120s | > 120s | Reduce concurrency or check DB latency |
| **Avg Agent Latency** | < 1000ms | 1-2s | > 2s | Check for slow queries or network issues |
| **Writes/sec** | > 100 | 50-100 | < 50 | Check DB pool exhaustion |
| **CPU %** | < 70% | 70-90% | > 90% | Adaptive concurrency will reduce |
| **Memory MB** | < 8GB | 8-12GB | > 12GB | Risk of OOM, reduce concurrency |
| **DB Connections** | < 50 | 50-55 | > 55 | Approaching Supabase limit |
| **Errors/cycle** | < 5 | 5-20 | > 20 | Investigate error types |

### Common Issues & Solutions

**Issue: High Cycle Time (> 120s)**
- **Cause:** Too many concurrent agents, DB bottleneck
- **Solution:** Reduce max_concurrent to 30 or check DB query performance

**Issue: Memory Usage > 12GB**
- **Cause:** Memory leak or too many agents in flight
- **Solution:** Reduce concurrency, check for uncollected objects, add GC

**Issue: Many "Connection Timeout" Errors**
- **Cause:** Supabase connection limit reached
- **Solution:** Reduce max_concurrent, check pool_size configuration

**Issue: LLM Rate Limit Errors (429)**
- **Cause:** Exceeding free tier limits
- **Solution:** Adaptive rate limiter will adjust, or upgrade to paid tier

---

## 10. Checklist for Production Run

### Pre-Run Checklist

- [ ] Verify Supabase connection limit (60 connections)
- [ ] Check Supabase disk space (> 10GB free)
- [ ] Ensure M1 Pro has > 4GB free RAM
- [ ] Test database connection pool with 50 connections
- [ ] Verify API rate limiting bypass works (X-Simulation-Mode header)
- [ ] Checkpoint directory exists and is writable
- [ ] Disable LangSmith tracing if not needed (saves overhead)
- [ ] Set appropriate log level (INFO for normal, DEBUG for debugging)

### During Run Checklist

- [ ] Monitor dashboard for warning/critical metrics
- [ ] Check checkpoint files are created every 5 minutes
- [ ] Watch error rate (should be < 5/cycle)
- [ ] Monitor CPU/memory usage
- [ ] Check Supabase dashboard for connection count
- [ ] Review log file for unexpected errors

### Post-Run Checklist

- [ ] Review final statistics
- [ ] Check CSV metrics file for anomalies
- [ ] Analyze error types and patterns
- [ ] Verify all 372 agents completed
- [ ] Check Supabase for orphaned transactions
- [ ] Clean up old checkpoints (keep last 10)
- [ ] Document any issues or optimizations

---

## 11. Rollback Plan

If issues occur:

1. **Immediate Stop:**
   ```bash
   # Press Ctrl+C to stop gracefully
   # Or send SIGTERM
   kill -TERM <pid>
   ```

2. **Resume from Checkpoint:**
   ```bash
   # Orchestrator will auto-detect latest checkpoint
   python -m app.simulation.orchestrator \
       --hours 6 \
       --time-scale 24 \
       --max-concurrent 30 \  # Reduce concurrency
       --resume
   ```

3. **Revert Configuration:**
   ```bash
   # Reduce concurrency
   export SIMULATION_MAX_CONCURRENT=20
   
   # Reduce DB pool
   # Edit app/main.py: pool_size=20
   ```

4. **Clean Up:**
   ```bash
   # Remove checkpoints
   rm -rf data/checkpoints/*
   
   # Clean simulation data
   python cleanup_simulation.py
   ```

---

## 12. Success Criteria

The 372-agent simulation will be considered successful when:

1. **All 372 agents complete** without crashes
2. **Cycle time < 60 seconds** (from start to all agents processed)
3. **Memory usage < 12GB** throughout run
4. **Error rate < 5%** (failed agents < 20)
5. **No database connection exhaustion** (max 55 concurrent)
6. **Checkpoints created** every 5 minutes
7. **Monitoring dashboard** updates in real-time
8. **Recovery from crash** possible via checkpoint
9. **Supabase limits not exceeded** (60 connections, storage, etc.)

---

## Appendix A: Command Reference

### Run Full Simulation (372 agents)
```bash
python -m app.simulation.orchestrator \
    --hours 6 \
    --time-scale 24 \
    --max-concurrent 50 \
    --checkpoint-interval 300 \
    --adaptive \
    --debug \
    --log-file simulation_$(date +%Y%m%d_%H%M%S).log
```

### Resume from Checkpoint
```bash
python -m app.simulation.orchestrator \
    --hours 6 \
    --time-scale 24 \
    --max-concurrent 50 \
    --resume
```

### Run with Specific Agents
```bash
python -m app.simulation.orchestrator \
    --hours 1 \
    --agents agent_001 agent_002 agent_003 \
    --max-concurrent 10 \
    --debug
```

### Quick Test (10 agents, no dashboard)
```bash
python -m app.simulation.orchestrator \
    --hours 0.5 \
    --max-concurrent 10 \
    --no-dashboard \
    --log-file test.log
```

---

## Appendix B: Troubleshooting Commands

### Check Database Connections
```bash
# In Supabase SQL Editor
SELECT count(*) FROM pg_stat_activity WHERE datname = 'postgres';
```

### Monitor Simulation Progress
```bash
# Watch checkpoint files
watch -n 5 'ls -lh data/checkpoints/'

# Tail log file
tail -f simulation_*.log | grep ERROR
```

### Check Resource Usage
```bash
# CPU and memory
top -pid $(pgrep -f orchestrator)

# Memory detailed
vmmap $(pgrep -f orchestrator) | head -50
```

### Kill Stuck Simulation
```bash
# Find process
pgrep -f orchestrator

# Kill gracefully
kill -TERM <pid>

# Force kill if needed
kill -9 <pid>
```

---

**Document Version:** 1.0  
**Last Updated:** January 2, 2026  
**Author:** Claude Code  
**Status:** Ready for Implementation
