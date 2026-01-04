# Scaling Simulation: Q&A, Assumptions, and Decision Log

> This document captures all questions asked, options considered, and decisions made during the scaling plan design process for scaling the simulation from 10 to 372 agents.

---

## Table of Contents

1. [Infrastructure Questions](#1-infrastructure-questions)
2. [Database Strategy](#2-database-strategy)
3. [Parallelization Strategy](#3-parallelization-strategy)
4. [Checkpoint & Resume Strategy](#4-checkpoint--resume-strategy)
5. [Error Handling & Resilience](#5-error-handling--resilience)
6. [API & Rate Limiting](#6-api--rate-limiting)
7. [Monitoring & Control](#7-monitoring--control)
8. [Agent Behavior](#8-agent-behavior)
9. [Implementation Planning](#9-implementation-planning)
10. [Key Assumptions](#10-key-assumptions)
11. [Open Questions & Future Considerations](#11-open-questions--future-considerations)

---

## 1. Infrastructure Questions

### Q1.1: Target Machine Specifications

**Question**: What's your target machine specs? (affects parallelization strategy - more cores enable process pools vs thread pools)

| Option | Description | Implications |
|--------|-------------|--------------|
| MacBook Pro M1/M2/M3 (8-12 cores, 16-32GB RAM) | Good for thread-based parallelism, limited by memory | Conservative approach needed |
| MacBook Pro M1/M2/M3 Max (12+ cores, 64-96GB RAM) | Can handle aggressive parallelization | More headroom |
| Cloud VM (configurable) | Pay-per-use, scalable | Variable cost |
| Linux workstation | Maximum performance | Dedicated hardware |

**Selected**: MacBook Pro M1/M2/M3 (8-12 cores, 16-32GB RAM)

**Rationale**: This is the actual hardware available. Constrains us to ~16GB RAM which requires efficient memory management.

---

### Q1.2: RAM Constraint

**Question**: What's your RAM constraint? This affects whether we can keep 372 agent states + HTTP connections + buffers in memory.

| Option | Description |
|--------|-------------|
| 16GB (conservative) | Need to be memory-efficient |
| 32GB (comfortable) | Good headroom for caching and buffers |
| No specific limit | Monitor and adjust |
| Memory tracking in dashboard | Monitor alongside other metrics |

**Selected**: 16GB (conservative, leave room for OS)

**Rationale**: Realistic constraint for MacBook Pro. Need to ensure simulation doesn't starve other processes.

**Memory Budget Calculation**:
- Agent state: 372 × 4KB = ~1.5MB
- HTTP sessions: 10 × 100KB = ~1MB
- asyncio tasks: 372 × 10KB = ~3.7MB
- DB connection pool: 50 × 5KB = ~250KB
- Buffers/caches: ~50MB
- **Total estimated**: ~60MB active (safe margin within 16GB)

---

### Q1.3: Database Location

**Question**: With 372 concurrent agents, are you testing against a local PostgreSQL or remote/cloud database?

| Option | Description | Implications |
|--------|-------------|--------------|
| Local PostgreSQL | Full control, shares resources | CPU competition |
| Supabase (cloud) | Connection limits, needs pooler | Network latency |
| Neon/PlanetScale | Auto-scaling, pay-per-query | Different pricing model |
| Remote dedicated PostgreSQL | Separate machine | Maximum control |

**Selected**: Supabase (cloud)

**Rationale**: Already using Supabase for the application. Need to work within its connection limits.

---

### Q1.4: Supabase Plan

**Question**: What's your Supabase plan? This determines connection limits.

| Option | Connection Limit | Pooler Available |
|--------|-----------------|------------------|
| Free tier | 60 direct | Yes |
| Pro ($25/month) | 100 direct | Yes |
| Team/Enterprise | Higher | Yes |
| Already using Supavisor | N/A | Pre-configured |

**Selected**: Pro ($25/month - 100 direct, pooler available)

**Recommendation Provided**: Use **Supavisor Transaction Mode** for this workload because:
1. High connection reuse (372 agents sharing ~50-100 connections)
2. Short-lived transactions (per-agent commits)
3. No need for prepared statements or session-level features
4. Better throughput than session mode

---

### Q1.5: API Target

**Question**: When all 372 agents hit cart/checkout APIs simultaneously, are these calling your FastAPI server running locally, or external APIs?

| Option | Description | Implications |
|--------|-------------|--------------|
| Local FastAPI (same machine) | Share CPU/RAM | Resource contention |
| Local FastAPI (separate container) | Dedicated resources | Still same machine |
| Remote deployed FastAPI | Separate infrastructure | True load testing |
| Direct DB operations | Bypass API | Faster but doesn't test API |

**Selected**: Remote FastAPI deployed on Railway

**Rationale**: Testing the actual production-like setup. Simulation runs locally, API is remote.

---

## 2. Database Strategy

### Q2.1: Write Safety Trade-off

**Question**: How do you want to handle the trade-off between simulation speed and database write safety?

| Option | Description | Risk Level |
|--------|-------------|------------|
| Batch writes (faster) | Commit every N cycles/seconds | Some data loss risk on crash |
| Per-cycle commits (balanced) | Commit after each cycle | Current approach |
| Per-agent commits (safest) | Commit after each agent | Slowest but safest |
| Async write queue | Background worker handles writes | Complex recovery |

**Selected**: Per-agent commits (safest, slower)

**Rationale**: Data integrity is critical for ML training data. Willing to trade speed for safety.

**Implementation**: Each agent's complete shopping flow commits independently. If one agent fails, others' data is preserved.

---

### Q2.2: Connection Pool Sizing

**Question**: Your current DB pool is 5 connections with 10 overflow. With 372 agents and per-agent commits, how aggressive do you want connection scaling?

| Option | Pool Size | Max Overflow | Total Capacity |
|--------|-----------|--------------|----------------|
| Conservative | 20 | 30 | 50 |
| Moderate | 50 | 75 | 125 |
| Aggressive | 100 | 150 | 250 |
| Per-worker model | Variable | Variable | Depends |

**Selected**: Moderate (50 pool, 75 overflow)

**Rationale**: Supabase Pro has 100 direct connections. With Supavisor transaction mode pooling, 50 base + 75 overflow provides good throughput while staying within limits.

---

## 3. Parallelization Strategy

### Q3.1: Agent Parallelism Target

**Question**: With 372 agents, how many do you want executing in parallel per cycle?

| Option | Description | Resource Impact |
|--------|-------------|-----------------|
| 8-10 agents | 1 per core | CPU-bound safe |
| 20-30 agents | Assumes I/O wait | Balanced |
| 50+ agents | Maximizes throughput | Memory pressure |
| Dynamic | Scale based on load | Adaptive |

**Selected**: All 372 agents in parallel

**User Clarification**: "I want all 372 to work in parallel. I am trying to replicate 372 users shopping on my app (DB writes + cart/checkout API calls)"

**Implication**: This is true concurrent load simulation, not batch processing. Architecture must support 372 simultaneous coroutines.

---

### Q3.2: Async Model

**Question**: Currently, agents run through LangGraph StateGraph synchronously. For 372 parallel agents, should we convert to async?

| Option | Description | Trade-offs |
|--------|-------------|------------|
| Keep sync, ProcessPoolExecutor | True parallelism, bypasses GIL | Higher memory per process |
| Convert to async with asyncio.gather | Single process, cooperative | GIL-bound for CPU work |
| Hybrid: async I/O, sync compute | Best of both worlds | More complex |
| Thread pool with sync code | Simple but GIL limits | Limited parallelism |

**Selected**: Hybrid: async I/O, sync compute

**Rationale**:
- LangGraph decision-making is CPU-bound (sync, run in thread pool)
- HTTP calls and DB operations are I/O-bound (async)
- This maximizes throughput while leveraging existing sync code

---

### Q3.3: Agent Flow Parallelization

**Question**: Each agent runs a multi-step shopping flow. How should steps be parallelized?

| Option | Description | Complexity |
|--------|-------------|------------|
| Sequential steps per agent, parallel agents | Agent A does all steps, Agent B does all steps, etc. | Simple |
| Batch by step across agents | All agents browse → all agents cart → all agents checkout | Medium |
| Pipeline with staggered starts | Natural load distribution | Medium |
| Event-driven with queues | Most flexible | High |

**Selected**: Sequential steps per agent, parallel agents

**Rationale**: Most natural model. Each agent completes their shopping flow independently. 372 agents run their flows concurrently.

---

### Q3.4: Warm-up Ramp

**Question**: Should the simulation support gradual ramp-up?

| Option | Description |
|--------|-------------|
| Yes, configurable warm-up period | Start low, add agents over time |
| Yes, automatic based on error rate | Scale up while healthy |
| No, start all immediately | Simpler |
| Configurable batches | Manual steps |

**Selected**: Yes, configurable warm-up period

**Implementation**:
```
Cycle 0-1: 37 agents (10%)
Cycle 2-3: 93 agents (25%)
Cycle 4-5: 186 agents (50%)
Cycle 6-7: 279 agents (75%)
Cycle 8+: 372 agents (100%)
```

---

### Q3.5: HTTP Session Management

**Question**: With 372 agents making API calls, how should HTTP client connections be pooled?

| Option | Description | Implications |
|--------|-------------|--------------|
| Shared aiohttp session (100 limit) | Single session, connection reuse | Simple |
| Multiple sessions by batch | 10 sessions, ~37 agents each | Isolate failures |
| Connection per agent | 372 connections | Resource heavy |
| httpx with configurable limits | Modern client | Different API |

**Selected**: Multiple sessions by agent batch (10 sessions, ~37 agents each)

**Session Assignment**: Static by agent ID hash (consistent assignment)

**Rationale**:
- Isolates failures (one bad session doesn't affect others)
- Hash-based assignment ensures agent always uses same session (predictable)
- 10 sessions × 37 agents = good balance

---

## 4. Checkpoint & Resume Strategy

### Q4.1: Checkpoint Granularity

**Question**: For checkpoint/resume, what granularity do you need to resume from?

| Option | Description | Complexity |
|--------|-------------|------------|
| Cycle-level | Resume from last completed cycle | Simple |
| Agent-level | Resume from last completed agent | Medium |
| Event-level | Resume from last persisted event | High |
| Time-based | Resume from last simulated timestamp | Medium |

**Selected**: Time-based - resume from last simulated timestamp

**Rationale**: Natural fit for time-scaled simulation. Resume based on where simulated time was, may re-run recent activity.

---

### Q4.2: Checkpoint File Format

**Question**: For checkpoint files, what format and storage location do you prefer?

| Option | Description | Pros/Cons |
|--------|-------------|-----------|
| JSON in ./data/checkpoints/ | Human-readable | Easy to inspect/edit |
| SQLite database file | Queryable, atomic | Handles complex state |
| Pickle/msgpack (binary) | Fast serialize | Not human-readable |
| Database table | No local files | Network dependent |

**Selected**: JSON file in ./data/checkpoints/

**Rationale**: Human-readable for debugging, easy to inspect state, simple implementation.

---

### Q4.3: Checkpoint Save Trigger

**Question**: What should trigger checkpoint saves?

| Option | Description |
|--------|-------------|
| Time-based (every N minutes) | Predictable |
| Cycle-based (every N cycles) | Progress-based |
| Event-based (milestones) | After X checkouts or Y errors |
| Manual trigger | User decides |

**Selected**: Cycle-based (every N cycles)

**Default**: Save every 10 cycles

---

### Q4.4: Checkpoint Timing

**Question**: When checkpoint saves, should it interrupt running operations?

| Option | Description |
|--------|-------------|
| Wait for cycle completion | Clean checkpoint at boundary |
| Checkpoint immediately | Mark in-progress agents |
| Async checkpoint | Non-blocking |
| Between agent batches | More frequent |

**Selected**: Wait for current cycle to complete

**Rationale**: Clean checkpoint at cycle boundary. All agents complete their work before state is saved.

---

### Q4.5: Resume Logic

**Question**: When resuming from checkpoint, should agents that already completed be skipped?

| Option | Description |
|--------|-------------|
| Skip completed, resume in-progress | Most efficient |
| Re-run everyone from cycle start | May duplicate data |
| Re-run but mark as 'replay' | Full re-run, flagged data |
| Idempotent operations | Safe to repeat |

**Selected**: Re-run but mark as 'replay' in DB

**Rationale**: Simpler than tracking per-agent state. Replayed data can be filtered in analytics if needed.

---

## 5. Error Handling & Resilience

### Q5.1: Failure Mode

**Question**: What's your acceptable simulation failure mode?

| Option | Description | Data Impact |
|--------|-------------|-------------|
| Fail fast | Stop all on any error | Consistent but loses progress |
| Isolate failures (current) | Continue other agents | May have partial data |
| Retry with backoff | Attempt recovery | More resilient |
| Circuit breaker | Pause on threshold | Controlled response |

**Selected**: Circuit breaker - pause on error threshold

**Threshold**: >5% of agents fail in one cycle (>18 of 372)

---

### Q5.2: Circuit Breaker Window

**Question**: For the circuit breaker's 5% failure threshold, what time window should this apply to?

| Option | Description |
|--------|-------------|
| Per cycle | React quickly to burst errors |
| Rolling 5-minute window | Smooth out temporary spikes |
| Rolling 10 cycles | Based on progress |
| Configurable | Adjust based on experience |

**Selected**: Per cycle (>18 failures in one cycle of 372)

**Rationale**: React quickly to burst errors. A sudden failure spike likely indicates a systemic issue.

---

### Q5.3: Circuit Breaker Behavior

**Question**: For the circuit breaker pause, what should happen?

| Option | Description |
|--------|-------------|
| Freeze and wait for manual resume | Investigate, then type 'resume' |
| Auto-retry after cooldown | Automatic recovery |
| Save state and exit | Checkpoint and exit |
| Notify and continue reduced | Alert, reduce parallelism |

**Selected**: Freeze and wait for manual resume

**Rationale**: Allows investigation of the issue before continuing. Prevents wasting cycles on a broken system.

---

### Q5.4: Failed Checkout Handling

**Question**: When an agent's checkout fails (e.g., API timeout), what should happen to their cart state?

| Option | Description |
|--------|-------------|
| Keep cart intact, retry next cycle | Realistic |
| Clear cart, start fresh | Clean slate |
| Mark as 'pending_retry' with expiration | Keep for N cycles |
| Log as abandoned | Treat as abandonment event |

**Selected**: Clear cart, start fresh next cycle

**Rationale**: Simplifies state management. Failed checkouts don't carry over stale data.

---

### Q5.5: API Outage Handling

**Question**: If the Railway API is down completely, what should the simulation do?

| Option | Description |
|--------|-------------|
| Pause immediately | Safe, no wasted cycles |
| Queue requests | Resilient but complex |
| Skip API-dependent steps | Partial progress |
| Auto-checkpoint and exit | Save state, exit cleanly |

**Selected**: Pause immediately, wait for manual resume

**Rationale**: No point in continuing if API is unavailable. Prevents accumulating failed operations.

---

### Q5.6: Orphaned Session Cleanup

**Question**: Should there be automatic session cleanup for agents that crashed mid-shopping?

| Option | Description |
|--------|-------------|
| Yes, clean up on startup | Clear carts, mark abandoned |
| No, preserve for debugging | Keep for investigation |
| Prompt user on startup | Ask whether to clean |
| Auto-cleanup with logging | Clean but log what was cleaned |

**Selected**: Yes, clean up orphaned sessions on startup

**Implementation**:
- On resume: Mark active sessions as 'abandoned'
- Clear cart items for all active agents
- Log what was cleaned for reference

---

## 6. API & Rate Limiting

### Q6.1: Rate Limiting Strategy

**Question**: How should the simulation handle Supabase/Railway rate limits or temporary failures?

| Option | Description |
|--------|-------------|
| Exponential backoff with jitter | Standard pattern |
| Token bucket rate limiter | Pre-emptive limiting |
| Adaptive rate limiting | Start fast, slow on 429s |
| Queue with worker pool | Natural rate limiting |

**Selected**: Token bucket rate limiter

**Rationale**: Pre-emptively limit requests to stay under limits. Prevents 429 errors rather than reacting to them.

---

### Q6.2: Rate Limit Target

**Question**: For the token bucket rate limiter, what's your target requests-per-second?

| Option | Description | Cycle Impact |
|--------|-------------|--------------|
| Conservative (50 req/s) | Safe for most Railway plans | ~7.5s per full cycle |
| Moderate (100 req/s) | Good for paid Railway | ~3.7s per cycle |
| Aggressive (200+ req/s) | Requires Railway Pro | <2s per cycle |
| Measure first | Find actual limits | Data-driven |

**Selected**: Conservative (50 req/s)

**Calculation at 50 req/s**:
- 150 active agents × 6 API calls = 900 calls/cycle
- At 50 req/s = 18 seconds for API work
- With 75-second cycles (time-scale 48) = 57 seconds buffer ✓

---

### Q6.3: Time-Scale Decision

**Question**: Given the cycle math, what time-scale should we use?

**Context Provided**: User's previous tests with 10 agents used time-scale 96 (37.5-second cycles).

**User Response**: "I can also work with lower time-scales of maybe up to 48. So let's keep it user-input and I will manually take care of that but start with time-scale of 48"

**Selected**: Start with time-scale 48 (75-second cycles)

**Math at time-scale 48**:
```
Cycle interval = 3600s / 48 = 75 seconds
API work time = ~18 seconds
Buffer = 75 - 18 = 57 seconds margin ✓
```

---

### Q6.4: Latency Tracking

**Question**: Should the simulation track and report API latency metrics?

| Option | Description |
|--------|-------------|
| Yes, aggregate p50/p95/p99 | Useful for performance |
| Yes, per-endpoint breakdown | Detailed metrics |
| No, just success/failure | Simpler |
| Optional flag | Off by default |

**Selected**: Yes, aggregate p50/p95/p99 latencies

**Implementation**: LatencyTracker class with rolling window of 1000 samples.

---

## 7. Monitoring & Control

### Q7.1: Dashboard Detail Level

**Question**: For terminal monitoring of 372 agents, what level of detail do you need?

| Option | Description |
|--------|-------------|
| Aggregate stats only | Total sessions, checkouts, errors |
| Per-agent status grid | Visual grid of each agent's state |
| Live event stream | Scrolling log of events |
| Dashboard + exportable metrics | Real-time + periodic export |

**Selected**: Aggregate stats only (current Rich dashboard)

**Rationale**: 372 agents is too many for individual tracking. Aggregate view is more useful.

---

### Q7.2: Dashboard Refresh Rate

**Question**: How frequently should stats refresh?

| Option | Description | CPU Impact |
|--------|-------------|------------|
| Real-time (100ms) | Instant feedback | High |
| Fast (500ms) | Good responsiveness | Medium |
| Normal (1-2s) | Current approach | Low |
| Slow (5s) with event updates | Low CPU | Very low |

**Selected**: Slow (5s) with event-based updates

**Rationale**: Reduces dashboard overhead during high-concurrency runs. Updates on significant events.

---

### Q7.3: Control Interface

**Question**: For pausing/resuming during a run, what control interface do you want?

| Option | Description |
|--------|-------------|
| Keyboard shortcuts (p/r/q) | Simple, immediate |
| Interactive prompt when paused | Menu with options |
| Unix signals | Scriptable |
| HTTP control endpoint | Remote control |

**Selected**: Keyboard shortcuts (p=pause, r=resume, q=quit)

**Additional**: c=checkpoint (manual save)

---

## 8. Agent Behavior

### Q8.1: Shopping Time Realism

**Question**: Should simulated shopping times be realistic or compressed?

| Option | Description |
|--------|-------------|
| Compressed | All agents act each cycle |
| Realistic distribution | Uses temporal preferences |
| Random stagger | Add random delays |
| Peak-hour simulation | Concentrate in certain hours |

**Selected**: Realistic distribution (agents have time preferences)

**Implementation**: Uses existing temporal preferences:
- `weekday_affinity` / `weekend_affinity`
- Time-of-day preferences
- `shopping_frequency` base probability

---

### Q8.2: Idle Agent Behavior

**Question**: For agents that don't shop in a cycle (due to temporal preferences), should they still consume rate limit budget?

| Option | Description |
|--------|-------------|
| Idle agents do nothing | No API calls |
| Idle agents browse without cart | Generates view events |
| Idle agents update state | Minor background activity |
| Configurable | Flag to control |

**Selected**: Idle agents can view products without cart activity

**Rationale**: Browsing generates events for ML training data even without checkout.

---

### Q8.3: Agent Selection

**Question**: How should the 372 agents be loaded?

| Option | Description |
|--------|-------------|
| All active agents from database | Natural selection |
| Specific agent_ids from config | Explicit list |
| Random sample | Different each run |
| Tag-based selection | Group by tags |

**Selected**: All active agents from database

**Query**: `SELECT * FROM agents WHERE status = 'active'`

---

### Q8.4: Data Tagging

**Question**: For data generated during simulation, how important is distinguishing 'test run' data from 'production' data?

| Option | Description |
|--------|-------------|
| is_simulated flag (current) | Single boolean |
| Add simulation_run_id | Tag for bulk delete |
| Separate schema/database | Complete isolation |
| Add detailed metadata | Rich tagging |

**Selected**: is_simulated flag is sufficient (current)

**Rationale**: Current approach works. Can filter simulation data in queries.

---

## 9. Implementation Planning

### Q9.1: Primary Goal

**Question**: What's your primary goal for this 372-agent simulation?

| Option | Description |
|--------|-------------|
| Generate training data volume | Throughput matters most |
| Load test the system | Find breaking points |
| Realistic user behavior | Accuracy over speed |
| All of the above | Balance everything |

**Selected**: Data volume + realistic user behavior (options 1 and 3)

**Rationale**: Need large dataset for ML training with accurate shopping patterns.

---

### Q9.2: Implementation Priority

**Question**: What's your implementation priority order for these scaling features?

| Option | Order |
|--------|-------|
| Parallelization first | 1. Parallel → 2. Checkpoint → 3. Monitoring → 4. Rate limiting |
| Safety first | 1. Checkpoint → 2. Parallel → 3. Rate limiting → 4. Monitoring |
| Protect external services first | 1. Rate limiting → 2. Parallel → 3. Checkpoint → 4. Monitoring |
| All in parallel | Implement everything together |

**Selected**: 1. Rate limiting → 2. Parallelization → 3. Checkpoint → 4. Monitoring

**Rationale**: Protect Railway API first before scaling up. Then enable parallelization with proper limits. Then add safety (checkpoint). Finally enhance visibility.

---

### Q9.3: Dry Run Mode

**Question**: Should there be a 'dry run' mode?

| Option | Description |
|--------|-------------|
| Yes, for testing | Useful for debugging |
| No, real data only | Simpler |
| Yes with logging | Dry run, log intended actions |
| Separate profile mode | Dedicated performance testing |

**Selected**: Yes, for testing parallelization without side effects

**Scope**: Configurable (--mock-api, --mock-db flags)

---

### Q9.4: Dry Run Scope

**Question**: For the dry-run mode, should it also mock the database or just the API?

| Option | Description |
|--------|-------------|
| Mock both | Pure simulation |
| Mock API only | Test DB scaling |
| Mock database only | Test API load |
| Configurable flags | Flexible combinations |

**Selected**: Configurable (--mock-api, --mock-db flags)

**Implementation**:
- `--mock-api`: Skip HTTP calls, return mock responses
- `--mock-db`: Skip database writes, log operations
- Can use both, either, or neither

---

### Q9.5: Future Scope

**Question**: Should the scaling plan include future considerations (distributed workers, Kubernetes, etc.)?

| Option | Description |
|--------|-------------|
| Yes, roadmap for 1000+ agents | Think ahead |
| Focus on 372 only | Solve current problem |
| Brief notes on options | Mention possibilities |
| Separate document | Keep focused |

**Selected**: Yes, include roadmap for 1000+ agents

**Included in plan**: Section on distributed architecture, Kubernetes, Celery, and database scaling options.

---

### Q9.6: Offer Engine Parallelization

**Question**: The offer engine runs refresh cycles. With 372 agents, should offer assignment be parallelized too?

| Option | Description |
|--------|-------------|
| Parallel with agent execution | Complex coordination |
| Sequential: refresh then run | Cleaner separation |
| Background refresh | Decoupled |
| Batch assignment | Single query |

**Selected**: Yes, parallel offer refresh with agent execution

**Implementation**: Offer refresh runs concurrently with agent shopping. Offers are assigned while agents shop.

---

### Q9.7: Reproducibility

**Question**: Should the simulation support 'replay' of a specific day's activity for reproducibility?

| Option | Description |
|--------|-------------|
| Yes, seed random with run_id | Same seed = same decisions |
| No, embrace randomness | Each run unique |
| Optional seed flag | Reproducible when needed |
| Record decisions for replay | Save decision log |

**Selected**: No, embrace randomness for variety

**Rationale**: Each run should generate unique data. Variety is valuable for ML training.

---

## 10. Key Assumptions

### Technical Assumptions

1. **Network Stability**: Assumes reasonably stable internet connection between local machine, Supabase, and Railway.

2. **Supabase Connection Limits**: Pro tier provides 100 direct connections. Supavisor pooler effectively multiplies this for short transactions.

3. **Railway Capacity**: Railway can handle 50 req/s sustained load. May need to adjust if rate limited.

4. **Memory Overhead**: 372 agents with associated state, connections, and buffers fit comfortably in 16GB RAM (~60MB estimated).

5. **LangGraph Performance**: Sync LangGraph invocations in thread pool don't block event loop significantly.

### Behavioral Assumptions

6. **Agent Activity Distribution**: ~40% of agents will be active (shopping) in any given cycle based on temporal preferences.

7. **API Call Volume**: Each active agent makes ~6 API calls per shopping session (browse, cart operations, coupon check, checkout).

8. **Checkout Success Rate**: Majority of shopping sessions complete successfully. Failures are exceptional.

### Operational Assumptions

9. **Manual Intervention**: Operator is available to respond to circuit breaker pauses within reasonable time.

10. **Checkpoint Frequency**: Every 10 cycles provides good balance between safety and overhead.

11. **Simulation Duration**: Runs may last hours. Need robust checkpoint/resume for long runs.

---

## 11. Open Questions & Future Considerations

### Unresolved Questions

1. **Railway Actual Rate Limits**: What are the actual rate limits on the Railway deployment? May need to measure empirically.

2. **Supabase Pooler Behavior**: How does Supavisor behave under sustained 372-connection load? May need tuning.

3. **Offer Engine Contention**: With parallel offer refresh and agent execution, potential for race conditions on coupon assignment?

4. **Memory Under Load**: Actual memory usage under full 372-agent load may differ from estimates. Need to monitor.

### Future Enhancements

1. **Metrics Export**: Add Prometheus/Grafana integration for historical metrics analysis.

2. **Alert Integration**: Slack/email alerts on circuit breaker trips.

3. **Web Dashboard**: Optional web UI for monitoring (alternative to terminal).

4. **Distributed Mode**: When scaling beyond 500 agents, implement worker distribution.

5. **A/B Testing**: Run different agent cohorts with different parameters to test offer strategies.

### Technical Debt Considerations

1. **LangGraph Async Migration**: Full async LangGraph would improve performance but requires significant refactoring.

2. **Connection Pool Monitoring**: Add pool utilization metrics to dashboard.

3. **Batch Database Operations**: Some operations could be batched for efficiency (e.g., event recording).

---

## Decision Summary Table

| Decision Area | Selected Option | Key Rationale |
|--------------|-----------------|---------------|
| Hardware | MacBook Pro M-series (16GB) | Available hardware |
| Database | Supabase Pro + Supavisor Transaction Mode | Existing infrastructure |
| Write Strategy | Per-agent commits | Data integrity for ML |
| Parallelism | All 372 concurrent | True load simulation |
| Async Model | Hybrid (async I/O, sync compute) | Best of both worlds |
| Rate Limit | 50 req/s token bucket | Conservative safety |
| Time Scale | 48 (75s cycles) | Adequate buffer |
| Checkpoint | Cycle-based, JSON files | Simple, inspectable |
| Error Handling | Circuit breaker (5% threshold) | Controlled failure response |
| Resume Strategy | Re-run with 'replay' flag | Simple implementation |
| Control | Keyboard shortcuts | Immediate control |
| Monitoring | Aggregate stats, p50/95/99 latency | Actionable metrics |

---

*Document generated: 2024-01-15*
*Interview conducted with project owner for scaling from 10 to 372 agents*
