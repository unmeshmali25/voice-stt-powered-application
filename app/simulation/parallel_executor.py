"""
Parallel agent executor for 372 concurrent agents.

Uses hybrid async model:
- asyncio.gather() for agent coordination
- ThreadPoolExecutor for synchronous LangGraph calls
- Per-agent database sessions from connection pool
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.simulation.agent.state import AgentState, create_initial_state
from app.simulation.agent.shopping_graph import get_shopping_graph
from app.simulation.agent.actions import ShoppingActions, set_actions, clear_actions
from app.simulation.rate_limiter import TokenBucket
from app.simulation.monitoring import LatencyTracker, CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from single agent execution."""

    agent_id: str
    success: bool
    should_shop: bool = False
    checkout_decision: Optional[str] = None
    events_created: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class CycleResult:
    """Result from executing all agents in a cycle."""

    cycle_number: int
    agents_processed: int
    agents_shopped: int
    checkouts_completed: int
    checkouts_abandoned: int
    events_created: int
    errors: int
    duration_seconds: float
    agent_results: List[AgentResult] = field(default_factory=list)


class ParallelAgentExecutor:
    """
    Execute agents in parallel using asyncio.gather() and ThreadPoolExecutor.

    Architecture:
    - Main event loop coordinates agent coroutines via asyncio.gather()
    - Each agent coroutine runs LangGraph synchronously in thread pool (non-blocking)
    - Each agent gets own database session from connection pool
    - Rate limiter controls API call rate across all agents
    - Circuit breaker pauses on excessive failures

    Usage:
        executor = ParallelAgentExecutor(
            db_url="postgresql://...",
            rate_limiter=TokenBucket(capacity=50),
        )

        cycle_result = await executor.execute_cycle(
            agents=agents,
            sim_date=sim_date,
            store_id="store-123",
            cycle_number=1,
        )
    """

    def __init__(
        self,
        db_url: str,
        rate_limiter: Optional[TokenBucket] = None,
        latency_tracker: Optional[LatencyTracker] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        max_workers: int = 12,
        pool_size: int = 50,
        max_overflow: int = 75,
        use_llm: bool = False,
    ):
        """
        Initialize parallel executor.

        Args:
            db_url: Database connection URL
            rate_limiter: Token bucket for rate limiting API calls
            latency_tracker: Tracker for recording agent execution latency
            circuit_breaker: Circuit breaker for failure handling
            max_workers: Thread pool size for LangGraph execution
            pool_size: Base database connection pool size
            max_overflow: Max additional connections under load
            use_llm: If True, use LLM decision routers; if False, use probability-based
        """
        self.db_url = db_url
        self.rate_limiter = rate_limiter
        self.latency_tracker = latency_tracker
        self.circuit_breaker = circuit_breaker
        self.max_workers = max_workers

        # Create engine with larger pool for parallel execution
        self.engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=30,
        )
        self.SessionFactory = sessionmaker(bind=self.engine)

        # Thread pool for synchronous LangGraph calls
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

        # Pre-compiled graph (shared, stateless)
        self.shopping_graph = get_shopping_graph(use_llm=use_llm)

        # Stop flag for graceful cancellation
        self._stop_requested = False
        self._current_tasks: List[asyncio.Task] = []

        logger.info(
            f"ParallelAgentExecutor initialized: "
            f"pool_size={pool_size}, max_overflow={max_overflow}, "
            f"max_workers={max_workers}"
        )

    async def execute_cycle(
        self,
        agents: List[Dict[str, Any]],
        sim_date: date,
        store_id: str,
        cycle_number: int,
    ) -> CycleResult:
        """
        Execute all agents for one cycle concurrently.

        Args:
            agents: List of agent records from database
            sim_date: Current simulated date
            store_id: Default store ID for shopping sessions
            cycle_number: Current cycle number

        Returns:
            CycleResult with aggregated statistics
        """
        start_time = time.time()

        # Check circuit breaker before starting
        if self.circuit_breaker and self.circuit_breaker.is_open():
            logger.warning("Circuit breaker is OPEN - skipping cycle execution")
            return CycleResult(
                cycle_number=cycle_number,
                agents_processed=0,
                agents_shopped=0,
                checkouts_completed=0,
                checkouts_abandoned=0,
                events_created=0,
                errors=0,
                duration_seconds=0.0,
            )

        # Reset circuit breaker for new cycle
        if self.circuit_breaker:
            self.circuit_breaker.reset_cycle()

        # Check if stop was requested before starting
        if self._stop_requested:
            logger.info("Stop requested before cycle start, returning empty result")
            return CycleResult(
                cycle_number=cycle_number,
                agents_processed=0,
                agents_shopped=0,
                checkouts_completed=0,
                checkouts_abandoned=0,
                events_created=0,
                errors=0,
                duration_seconds=0.0,
            )

        # Create tasks for all agents
        tasks = [
            asyncio.create_task(self._execute_agent(agent, sim_date, store_id))
            for agent in agents
        ]
        self._current_tasks = tasks

        try:
            # Run all agents concurrently, collect results (including exceptions)
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            logger.info(f"Cycle {cycle_number} cancelled due to stop request")
            # Cancel any pending tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Wait briefly for cancellations to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            return CycleResult(
                cycle_number=cycle_number,
                agents_processed=0,
                agents_shopped=0,
                checkouts_completed=0,
                checkouts_abandoned=0,
                events_created=0,
                errors=0,
                duration_seconds=time.time() - start_time,
            )
        finally:
            self._current_tasks = []

        # Process results
        agent_results = []
        agents_shopped = 0
        checkouts_completed = 0
        checkouts_abandoned = 0
        events_created = 0
        errors = 0

        for agent, result in zip(agents, results):
            agent_id = agent.get("agent_id", "unknown")

            if isinstance(result, Exception):
                # Agent execution failed with exception
                agent_results.append(
                    AgentResult(
                        agent_id=agent_id,
                        success=False,
                        error=str(result)[:500],
                    )
                )
                errors += 1
                logger.error(f"Agent {agent_id} failed with exception: {result}")

                # Record failure in circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(agent_id, result)

            elif isinstance(result, AgentResult):
                agent_results.append(result)

                if result.success:
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success()

                    if result.should_shop:
                        agents_shopped += 1
                        events_created += result.events_created

                        if result.checkout_decision == "complete":
                            checkouts_completed += 1
                        elif result.checkout_decision == "abandon":
                            checkouts_abandoned += 1
                else:
                    errors += 1
                    if self.circuit_breaker and result.error:
                        self.circuit_breaker.record_failure(
                            agent_id, Exception(result.error)
                        )
            else:
                # Unexpected result type
                logger.warning(
                    f"Agent {agent_id} returned unexpected result type: {type(result)}"
                )
                errors += 1

        duration = time.time() - start_time

        return CycleResult(
            cycle_number=cycle_number,
            agents_processed=len(agents),
            agents_shopped=agents_shopped,
            checkouts_completed=checkouts_completed,
            checkouts_abandoned=checkouts_abandoned,
            events_created=events_created,
            errors=errors,
            duration_seconds=duration,
            agent_results=agent_results,
        )

    async def _execute_agent(
        self,
        agent: Dict[str, Any],
        sim_date: date,
        store_id: str,
    ) -> AgentResult:
        """
        Execute single agent with own DB session.

        Runs LangGraph synchronously in thread pool to avoid blocking event loop.

        Args:
            agent: Agent record from database
            sim_date: Current simulated date
            store_id: Default store ID

        Returns:
            AgentResult with execution outcome
        """
        agent_id = agent.get("agent_id", "unknown")
        start_time = time.time()

        # Get own database session from pool
        db = self.SessionFactory()

        try:
            # Rate limit before execution (if configured)
            if self.rate_limiter:
                await self.rate_limiter.wait_and_acquire(tokens=1)

            # Run LangGraph in thread pool (sync invoke -> async wrapper)
            loop = asyncio.get_event_loop()
            final_state = await loop.run_in_executor(
                self.thread_pool,
                self._run_graph_sync,
                agent,
                sim_date,
                store_id,
                db,
            )

            # Commit changes
            db.commit()

            duration_ms = (time.time() - start_time) * 1000

            # Record latency
            if self.latency_tracker:
                self.latency_tracker.record("agent_execution", duration_ms)

            return AgentResult(
                agent_id=agent_id,
                success=True,
                should_shop=final_state.get("should_shop", False),
                checkout_decision=final_state.get("checkout_decision"),
                events_created=final_state.get("events_created", 0),
                duration_ms=duration_ms,
            )

        except Exception as e:
            db.rollback()
            duration_ms = (time.time() - start_time) * 1000

            # Detailed error logging
            import traceback

            error_details = f"{e}\n{traceback.format_exc()}"
            logger.error(f"Agent {agent_id} execution failed: {error_details}")

            # Also print to console to ensure visibility
            print(f"❌ AGENT ERROR - {agent_id}: {str(e)}")

            # Record error latency
            if self.latency_tracker:
                self.latency_tracker.record_error("agent_execution")

            return AgentResult(
                agent_id=agent_id,
                success=False,
                error=str(e)[:500],
                duration_ms=duration_ms,
            )
        finally:
            db.close()

    def _run_graph_sync(
        self,
        agent: Dict[str, Any],
        sim_date: date,
        store_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Synchronous LangGraph execution (runs in thread pool).

        Sets up thread-local ShoppingActions instance for this agent.

        Args:
            agent: Agent record
            sim_date: Simulated date
            store_id: Store ID
            db: Database session for this agent

        Returns:
            Final agent state from graph execution
        """
        # Set thread-local actions instance for this agent
        set_actions(db)

        try:
            # Create initial state
            initial_state = create_initial_state(
                agent=agent,
                simulated_date=sim_date,
                store_id=store_id,
                db=db,
            )

            # Execute graph
            agent_id = agent.get("agent_id", "unknown")
            config = {"configurable": {"thread_id": agent_id}}

            final_state = self.shopping_graph.invoke(initial_state, config)

            return final_state

        finally:
            # Clear thread-local actions (optional cleanup)
            clear_actions()

    def stop(self) -> None:
        """Request immediate stop of ongoing cycle execution."""
        logger.info("Stop requested for ParallelAgentExecutor...")
        self._stop_requested = True

        # Cancel any in-flight asyncio tasks
        if self._current_tasks:
            cancelled = 0
            for task in self._current_tasks:
                if not task.done():
                    task.cancel()
                    cancelled += 1
            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} pending agent tasks")

    def shutdown(self, wait: bool = False) -> None:
        """
        Clean up resources.

        Args:
            wait: If True, wait for pending tasks to complete (slow shutdown).
                 If False, cancel tasks immediately (fast shutdown).
        """
        logger.info(f"Shutting down ParallelAgentExecutor (wait={wait})...")

        # Always try to cancel first for faster shutdown
        if not wait and self._current_tasks:
            self.stop()

        # Shutdown thread pool
        self.thread_pool.shutdown(wait=wait)
        self.engine.dispose()
        logger.info("ParallelAgentExecutor shutdown complete")

    def get_pool_status(self) -> Dict[str, Any]:
        """Get database connection pool status."""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }


class WarmupController:
    """
    Gradually ramp up agent count during warmup.

    Useful for stress testing and avoiding thundering herd on startup.

    Usage:
        warmup = WarmupController(total_agents=372, warmup_cycles=10)

        for cycle in range(100):
            active_count = warmup.get_active_agent_count()
            agents_to_run = all_agents[:active_count]
            # Execute agents...
            warmup.advance()
    """

    def __init__(
        self,
        total_agents: int,
        warmup_cycles: int = 10,
        warmup_batches: Optional[List[float]] = None,
    ):
        """
        Initialize warmup controller.

        Args:
            total_agents: Total number of agents
            warmup_cycles: Number of cycles to reach full capacity
            warmup_batches: Percentage thresholds (default: [0.1, 0.25, 0.5, 0.75, 1.0])
        """
        self.total_agents = total_agents
        self.warmup_cycles = warmup_cycles
        self.warmup_batches = warmup_batches or [0.1, 0.25, 0.5, 0.75, 1.0]
        self.current_cycle = 0

    def get_active_agent_count(self) -> int:
        """Get number of agents for current cycle."""
        if self.current_cycle >= self.warmup_cycles:
            return self.total_agents

        progress = self.current_cycle / self.warmup_cycles

        # Find appropriate batch level
        for threshold in self.warmup_batches:
            if progress < threshold:
                return max(1, int(self.total_agents * threshold))

        return self.total_agents

    def advance(self) -> None:
        """Advance to next cycle."""
        self.current_cycle += 1

    def is_warmup_complete(self) -> bool:
        """Check if warmup is complete."""
        return self.current_cycle >= self.warmup_cycles

    def reset(self) -> None:
        """Reset warmup to beginning."""
        self.current_cycle = 0

    def get_status(self) -> Dict[str, Any]:
        """Get warmup status."""
        return {
            "current_cycle": self.current_cycle,
            "warmup_cycles": self.warmup_cycles,
            "active_agents": self.get_active_agent_count(),
            "total_agents": self.total_agents,
            "is_complete": self.is_warmup_complete(),
            "progress_percent": min(
                100, int(self.current_cycle / self.warmup_cycles * 100)
            ),
        }
