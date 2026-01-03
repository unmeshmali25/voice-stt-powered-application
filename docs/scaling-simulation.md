# Scaling Simulation Plan: 372 Agents

This document outlines the architectural and technical strategy for scaling the VoiceOffers simulation from 10 to 372+ concurrent agents, targeting a `time_scale` of 48x-96x on an M1 Pro MacBook Pro (8 cores, 16GB RAM) hitting a Railway-hosted API and a Supabase Pro database.

## 1. Architectural Strategy: Batched Async Concurrency

To handle 372 agents without overwhelming the local machine or the remote database/API, we will move from sequential processing to **Batched Asynchronous Execution**.

### Batched Execution
- **Mechanism:** Use `asyncio.Semaphore` or chunked lists to process agents in batches (e.g., 50 agents at a time).
- **Rationale:** 
    - Full parallelism (all 372 at once) risks hitting Supabase connection limits and causing high local RAM spikes.
    - Sequential processing is too slow for 96x time scale.
- **Implementation:**
    ```python
    async def _run_cycle(self, agents):
        batch_size = 50
        for i in range(0, len(agents), batch_size):
            batch = agents[i:i + batch_size]
            tasks = [self._run_agent(agent, sim_date) for agent in batch]
            await asyncio.gather(*tasks)
    ```

## 2. Remote Interaction Strategy (Hybrid)

As per requirements, the simulation will target the **Railway Remote Server** for core business logic.

### API-Driven Actions
- Use `httpx` for asynchronous HTTP calls to:
    - `POST /api/cart/add`
    - `POST /api/orders/checkout`
    - `POST /api/offers/assign`
- **Benefit:** Validates server-side load handling, rate limiting, and end-to-end flow.

### Direct DB Fallback
- Continue using SQLAlchemy for:
    - Initial agent loading.
    - Reading product catalogs (cached locally).
    - Writing low-level simulation metrics not exposed by APIs.

## 3. Database & Connection Pooling

### Supabase Pro Optimization
- **Connection Pool:** Increase SQLAlchemy `pool_size` to 20 and `max_overflow` to 40.
- **PgBouncer:** Use Supabase's transaction mode connection string (port 6543) to handle the surge in concurrent writes from batched agents.
- **Statement Timeout:** Set a reasonable `statement_timeout` to prevent hung transactions from blocking the pool.

## 4. Checkpoint & Recovery (Resiliency)

The simulation must be "crash-proof" for long runs.

### Resumption Logic
- **Simulation Time:** On startup, the orchestrator will query the `shopping_sessions` or `orders` table for the latest `created_at` timestamp.
- **Automatic Offset:** If the script restarts, it will default the `start_date` to this last recorded timestamp + 1 simulated hour.
- **State Persistence:** Each agent's "should shop today" decision will be recorded in a `simulation_state` table to prevent double-shopping if a crash occurs mid-cycle.

## 5. Monitoring & Visibility

### Enhanced Rich Dashboard
- **Progress Bars:** Add a per-batch progress bar.
- **Throughput Metrics:** "Orders/min" and "API Latency" tracking.
- **Error Tracking:** Separate counters for "DB Errors" vs "API 5xx Errors".

### Logging
- **Structured Logs:** Output to `simulation_runs.log` in JSON format for easier analysis of failures post-run.

## 6. Resource Management (M1 Pro Optimization)

- **RAM Control:** Agents currently load metadata. We will implement a singleton `CatalogCache` to share product and store data across all 372 agent instances, reducing memory footprint by ~60%.
- **CPU:** 8 cores is plenty for `asyncio`, as the bottleneck will be remote I/O (Railway/Supabase). We will avoid `multiprocessing` to keep memory usage low.

## 7. Implementation Roadmap

1. **Phase 1 (Resiliency):** Update `SimulationOrchestrator` to fetch start time from DB.
2. **Phase 2 (Concurrency):** Refactor `_run_cycle` to use batched `asyncio.gather`.
3. **Phase 3 (Networking):** Create `RemoteShoppingActions` using `httpx` to replace direct DB writes for cart/checkout.
4. **Phase 4 (Pooling):** Tune SQLAlchemy engine settings for Supabase remote connection.
5. **Phase 5 (Monitoring):** Integrate API latency tracking into the Rich Dashboard.
