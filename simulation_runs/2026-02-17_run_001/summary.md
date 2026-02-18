# Simulation Run: 2026-02-17_run_001

## Run Overview

| Metric | Value |
|--------|-------|
| **Real Duration** | 10.00 hours |
| **Simulated Duration** | ~92 days (2022-05-14 → 2022-08-14) |
| **Time Scale** | 96x (1 real second = 96 simulated seconds) |
| **Mode** | Parallel |
| **Errors** | 0 |

## Performance Metrics

| Metric | Value |
|--------|-------|
| **Cycles Completed** | 926 |
| **Agents Processed** | 342,620 |
| **Requests Made** | 342,620 |
| **Latency p50/p95** | 149ms / 202ms |
| **Rate Limit** | 50 req/s |
| **Circuit Breaker** | Closed (healthy) |

## Shopping Behavior

| Metric | Value |
|--------|-------|
| **Agents Shopped** | 2,944 |
| **Sessions Created** | 2,944 |
| **Checkouts Completed** | 1,718 |
| **Checkouts Abandoned** | 1,226 |
| **Abandon Rate** | 41.7% |
| **Shop Rate** | 0.86% of processed agents |

## Business Metrics

| Metric | Value |
|--------|-------|
| **Offers Assigned** | 67,104 |
| **Events Created** | 19,767 |
| **Avg Offers per Shopper** | 22.8 |
| **Avg Events per Session** | 6.7 |

## Simulation Config

- **Time Scale**: 96.0x
- **Default Store ID**: `ebb4d8a1-4695-46f0-844b-7f41ed13bd59`
- **Process All Agents**: false
- **Rate Limit**: 50 req/s
- **Checkpoint Interval**: 10 cycles

## Notes

- Simulation ran cleanly with zero errors
- Circuit breaker remained closed throughout (no cascade failures)
- LangSmith tracing was OFF for this run
- Started: 2026-02-17 ~11:11
- Ended: 2026-02-17 21:11
