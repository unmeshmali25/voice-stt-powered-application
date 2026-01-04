"""
Simulation Orchestrator - Coordinates time advancement and agent execution.

This module provides:
- SimulationOrchestrator: Main coordinator class
- Rich terminal dashboard for monitoring
- Integration with LangGraph agents and offer engine
- Parallel agent execution for 372+ agents
- Checkpoint/resume for crash recovery
- Rate limiting for API protection
"""

import asyncio
import time
import logging
import os
import sys
import signal
import traceback
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from io import StringIO

from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session, sessionmaker
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.logging import RichHandler

from app.offer_engine import get_scheduler, get_config, reset_singletons
from app.simulation.agent.state import AgentState, create_initial_state
from app.simulation.agent.actions import set_actions, get_actions
from app.simulation.agent.shopping_graph import get_shopping_graph

# Scaling components
from app.simulation.rate_limiter import get_rate_limiter, get_rate_limiter_metrics
from app.simulation.parallel_executor import ParallelAgentExecutor, WarmupController
from app.simulation.checkpoint import CheckpointManager
from app.simulation.monitoring import LatencyTracker, MemoryMonitor, CircuitBreaker

logger = logging.getLogger(__name__)


class LogBuffer(logging.Handler):
    """Custom logging handler that stores recent log messages in memory."""

    def __init__(self, max_lines: int = 50):
        super().__init__()
        self.max_lines = max_lines
        self.buffer: List[str] = []

    def emit(self, record):
        """Add log record to buffer."""
        try:
            msg = self.format(record)
            timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            formatted = f"[{timestamp}] [{record.levelname}] {msg}"
            self.buffer.append(formatted)
            if len(self.buffer) > self.max_lines:
                self.buffer.pop(0)
        except Exception:
            self.handleError(record)

    def get_lines(self) -> List[str]:
        """Get all buffered lines."""
        return self.buffer.copy()

    def clear(self):
        """Clear the buffer."""
        self.buffer.clear()


@dataclass
class SimulationStats:
    """Tracks simulation statistics."""

    start_time: float = field(default_factory=time.time)
    simulated_datetime: Optional[datetime] = None
    cycles_completed: int = 0
    agents_processed: int = 0
    agents_shopped: int = 0
    sessions_created: int = 0
    checkouts_completed: int = 0
    checkouts_abandoned: int = 0
    offers_assigned: int = 0
    events_created: int = 0
    errors: int = 0
    last_error: str = ""

    def elapsed_hours(self) -> float:
        return (time.time() - self.start_time) / 3600

    def to_dict(self) -> Dict[str, Any]:
        return {
            "elapsed_hours": round(self.elapsed_hours(), 2),
            "simulated_datetime": str(self.simulated_datetime)
            if self.simulated_datetime
            else None,
            "cycles_completed": self.cycles_completed,
            "agents_processed": self.agents_processed,
            "agents_shopped": self.agents_shopped,
            "sessions_created": self.sessions_created,
            "checkouts_completed": self.checkouts_completed,
            "checkouts_abandoned": self.checkouts_abandoned,
            "offers_assigned": self.offers_assigned,
            "events_created": self.events_created,
            "errors": self.errors,
        }


class SimulationOrchestrator:
    """
    Main simulation coordinator.

    Manages:
    - Time advancement via OfferScheduler
    - Agent execution via LangGraph
    - Statistics tracking
    - Rich terminal dashboard
    """

    def __init__(
        self,
        db: Session,
        time_scale: float = 24.0,
        default_store_id: Optional[str] = None,
        process_all_agents: bool = True,
        debug_mode: bool = False,
        # Scaling parameters
        rate_limit_rps: int = 50,
        checkpoint_interval: int = 10,
        warmup_cycles: int = 0,
        parallel_mode: bool = True,
        db_url: Optional[str] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            db: SQLAlchemy Session
            time_scale: Time compression ratio (24 = 1 real hour = 24 simulated hours)
                        This overrides TIME_SCALE environment variable.
            default_store_id: Default store for shopping sessions
            process_all_agents: If True, scheduler processes all agents. If False, only processes filtered agents
            debug_mode: Enable debug logging in dashboard
            rate_limit_rps: API rate limit in requests per second
            checkpoint_interval: Cycles between checkpoint saves (0 to disable)
            warmup_cycles: Number of cycles to gradually ramp up agents (0 to disable)
            parallel_mode: Enable parallel agent execution (vs sequential)
            db_url: Database URL for parallel executor (uses env if None)
        """
        self.db = db
        self.time_scale = time_scale
        self.default_store_id = default_store_id or self._get_default_store()
        self.process_all_agents = process_all_agents
        self.debug_mode = debug_mode
        self.parallel_mode = parallel_mode
        self.rate_limit_rps = rate_limit_rps
        self.checkpoint_interval = checkpoint_interval
        self.warmup_cycles = warmup_cycles

        # Store db_url for parallel executor
        self._db_url = db_url or os.getenv("DATABASE_URL", "")
        if self._db_url.startswith("postgres://"):
            self._db_url = self._db_url.replace("postgres://", "postgresql://", 1)

        # Reset offer engine singletons for fresh initialization
        logger.info("Resetting offer engine singletons...")
        reset_singletons()
        logger.info("Creating new scheduler...")

        # Initialize offer engine
        self.scheduler = get_scheduler(db)

        # Sync time_scale if CLI parameter differs from env config
        if self.time_scale != self.scheduler.config.time_scale:
            old_scale = self.scheduler.config.time_scale
            self.scheduler.config.time_scale = self.time_scale
            logger.info(
                f"Updated scheduler time_scale to {self.time_scale} (was {old_scale})"
            )

        # Log final time_scale values for debugging
        logger.info(
            f"Orchestrator time_scale: {self.time_scale}, "
            f"scheduler.config.time_scale: {self.scheduler.config.time_scale}, "
            f"time_service.config.time_scale: {self.scheduler.time_service.config.time_scale}"
        )

        # Initialize actions (for sequential mode)
        set_actions(db)

        # Get shopping graph
        self.shopping_graph = get_shopping_graph()

        # Stats
        self.stats = SimulationStats()

        # Rich console
        self.console = Console()

        # Control flag
        self._stop_requested = False
        self._paused = False

        # Agent filtering
        self.agent_ids: Optional[List[str]] = None

        # Error log file
        self._error_log_path = "simulation_errors.log"
        self._clear_error_log()

        # Log buffer for debug mode
        self.log_buffer = LogBuffer(max_lines=20)
        if debug_mode:
            self._setup_debug_logging()

        # === Scaling Components ===

        # Rate limiter
        self.rate_limiter = get_rate_limiter(
            name="railway_api",
            capacity=rate_limit_rps,
            refill_rate=float(rate_limit_rps),
        )
        logger.info(f"Rate limiter initialized: {rate_limit_rps} req/s")

        # Latency tracker
        self.latency_tracker = LatencyTracker(window_size=1000)

        # Memory monitor
        self.memory_monitor = MemoryMonitor(warning_threshold_mb=12000)

        # Circuit breaker (initialized later when we know agent count)
        self.circuit_breaker: Optional[CircuitBreaker] = None

        # Checkpoint manager
        self.checkpoint_manager = CheckpointManager(
            checkpoint_dir=Path("./data/checkpoints"),
            save_interval_cycles=checkpoint_interval,
        ) if checkpoint_interval > 0 else None

        # Parallel executor (initialized later when we know db_url)
        self.parallel_executor: Optional[ParallelAgentExecutor] = None

        # Warmup controller (initialized later when we know agent count)
        self.warmup_controller: Optional[WarmupController] = None

    def _setup_debug_logging(self):
        """Setup debug logging to capture to buffer."""
        self.log_buffer.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        self.log_buffer.setFormatter(formatter)
        logging.getLogger().addHandler(self.log_buffer)

    def _initialize_scaling_components(self, agent_count: int):
        """Initialize scaling components that depend on agent count."""
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            total_agents=agent_count,
            on_open_callback=self._on_circuit_open,
        )
        logger.info(f"Circuit breaker initialized: threshold={self.circuit_breaker.failure_threshold}")

        # Warmup controller
        if self.warmup_cycles > 0:
            self.warmup_controller = WarmupController(
                total_agents=agent_count,
                warmup_cycles=self.warmup_cycles,
            )
            logger.info(f"Warmup controller initialized: {self.warmup_cycles} cycles")

        # Parallel executor (only if parallel mode enabled)
        if self.parallel_mode and self._db_url:
            self.parallel_executor = ParallelAgentExecutor(
                db_url=self._db_url,
                rate_limiter=self.rate_limiter,
                latency_tracker=self.latency_tracker,
                circuit_breaker=self.circuit_breaker,
                max_workers=12,
                pool_size=50,
                max_overflow=75,
            )
            logger.info("Parallel executor initialized")

    async def _on_circuit_open(self, circuit_breaker: CircuitBreaker):
        """Handle circuit breaker opening."""
        self._paused = True
        self.console.print("\n[red bold]=" * 60)
        self.console.print("[red bold]CIRCUIT BREAKER OPEN - Simulation PAUSED")
        self.console.print(f"[red]Failures this cycle: {circuit_breaker.cycle_failures}")
        self.console.print(f"[red]Threshold: {circuit_breaker.failure_threshold} (5%)")
        self.console.print("[yellow]Press 'r' to resume after investigating the issue")
        self.console.print("[red bold]=" * 60 + "\n")

    def request_stop(self):
        """Request immediate stop of simulation."""
        self._stop_requested = True
        logger.info("Stop requested, aborting current operation...")

    def _clear_error_log(self):
        """Clear or create error log file with header."""
        with open(self._error_log_path, "w") as f:
            f.write(f"VoiceOffers Simulation Error Log - {datetime.now()}\n")
            f.write("=" * 80 + "\n\n")

    def _log_error_to_file(self, error_msg: str):
        """Append error message to error log file."""
        with open(self._error_log_path, "a") as f:
            f.write(f"[{datetime.now()}]\n{error_msg}\n")
            f.write("-" * 80 + "\n\n")

    async def run(
        self,
        duration_hours: float,
        agent_ids: Optional[List[str]] = None,
        num_agents: Optional[int] = None,
        show_dashboard: bool = True,
        start_date: Optional[date] = None,
    ) -> SimulationStats:
        """
        Run simulation for specified duration.

        Args:
            duration_hours: Real-time hours to run
            agent_ids: Specific agent IDs to run, or None for all active
            num_agents: Number of agents to randomly select (overrides agent_ids if specified)
            show_dashboard: Show Rich terminal dashboard
            start_date: Simulated calendar start date (default: 2024-01-01)

        Returns:
            Final SimulationStats
        """
        logger.info(f"Starting simulation: {duration_hours}h at {self.time_scale}x")

        # Store agent IDs for scheduler filtering
        self.agent_ids = agent_ids

        # Load agents
        agents = self._load_agents(agent_ids, num_agents)
        logger.info(f"Loaded {len(agents)} agents")

        if not agents:
            logger.error("No agents found!")
            return self.stats

        # Initialize scaling components that depend on agent count
        self._initialize_scaling_components(len(agents))

        # Ensure simulation is started
        is_active = self.scheduler.time_service.is_simulation_active()
        logger.info(f"Simulation active check: {is_active}")
        logger.info(f"  simulation_mode: {self.scheduler.config.simulation_mode}")
        logger.info(
            f"  time_service._is_active: {self.scheduler.time_service._is_active}"
        )
        logger.info(f"  requested start_date: {start_date}")

        if not is_active:
            calendar_start = start_date or date(2024, 1, 1)
            logger.info(f"Starting simulation at {calendar_start}")
            self.scheduler.time_service.start_simulation(calendar_start=calendar_start)
            logger.info(
                f"Simulation started. Active: {self.scheduler.time_service.is_simulation_active()}"
            )
            should_initialize = True  # Track if this is a fresh start (for initialization)
        else:
            logger.warning(
                "Simulation already active, skipping start_simulation() call"
            )
            should_initialize = False  # Skip initialization on resume

        # Initialize all agents with offers BEFORE first cycle
        if should_initialize:
            logger.info("=" * 80)
            logger.info("STEP 1: Initializing agents with offers...")
            logger.info("=" * 80)

            try:
                # Pass a lambda to check stop status
                init_result = self.scheduler.initialize_all_agents(
                    agent_ids=self.agent_ids,
                    process_all=self.process_all_agents,
                    should_stop_check=lambda: self._stop_requested
                )

                # Check if initialization was aborted
                if self._stop_requested:
                    logger.warning("Initialization aborted by user")
                    return self.stats

                # Update stats with initialization results
                self.stats.offers_assigned += init_result.offers_assigned

                logger.info(
                    f"Initialization complete: {init_result.users_refreshed} agents initialized, "
                    f"{init_result.offers_assigned} offers assigned"
                )

                if init_result.offers_assigned == 0:
                    logger.error(
                        "WARNING: No offers were assigned during initialization! "
                        "This may indicate a problem with the coupon pool or database state."
                    )

            except Exception as e:
                logger.error(f"Failed to initialize agents: {e}")
                import traceback
                traceback.print_exc()
                # Continue anyway - the refresh logic will catch them later

            logger.info("=" * 80)
            logger.info("STEP 2: Starting simulation cycles...")
            logger.info("=" * 80)
        else:
            logger.info("Skipping initialization (resuming existing simulation)")

        # Calculate timing
        # Each cycle advances 1 simulated hour. Interval calculated to achieve time_scale cycles per real hour.
        # At time_scale=96: 37.5 real seconds per cycle (3600/96)
        # Results in 96 cycles per real hour, each advancing 1 simulated hour.
        advance_interval_seconds = 3600 / self.time_scale

        start_time = time.time()
        target_end_time = start_time + (duration_hours * 3600)

        if show_dashboard:
            with Live(
                self._build_dashboard(), refresh_per_second=1, console=self.console
            ) as live:
                self._setup_signal_handlers()
                try:
                    await self._run_loop(
                        agents, target_end_time, advance_interval_seconds, live
                    )
                finally:
                    self._cleanup_signal_handlers()
        else:
            self._setup_signal_handlers()
            try:
                await self._run_loop(
                    agents, target_end_time, advance_interval_seconds, None
                )
            finally:
                self._cleanup_signal_handlers()

        logger.info(f"Simulation complete. Stats: {self.stats.to_dict()}")

        if self.stats.errors > 0:
            self.console.print(f"\n[red]⚠ {self.stats.errors} error(s) occurred[/red]")
            self.console.print(f"[dim]Check {self._error_log_path} for details[/dim]")

        return self.stats

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigtstp = signal.getsignal(signal.SIGTSTP)

        def handle_interrupt(signum, frame):
            """Handle Ctrl+C and Ctrl+Z."""
            if signum == signal.SIGINT:
                self.console.print("\n[yellow]⚠ Ctrl+C detected - Stopping simulation immediately...[/yellow]")
                self.request_stop()
            elif signum == signal.SIGTSTP:
                self.console.print("\n[yellow]⚠ Ctrl+Z detected - Stopping simulation immediately...[/yellow]")
                self.request_stop()

        signal.signal(signal.SIGINT, handle_interrupt)
        signal.signal(signal.SIGTSTP, handle_interrupt)

    def _cleanup_signal_handlers(self):
        """Restore original signal handlers."""
        if hasattr(self, "_original_sigint") and self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if hasattr(self, "_original_sigtstp") and self._original_sigtstp:
            signal.signal(signal.SIGTSTP, self._original_sigtstp)

    async def _run_loop(
        self,
        agents: List[Dict[str, Any]],
        target_end_time: float,
        interval_seconds: float,
        live: Optional[Live],
    ):
        """Main simulation loop."""
        while time.time() < target_end_time and not self._stop_requested:
            # Track when this cycle started
            cycle_start_time = time.time()

            # Check if paused (circuit breaker)
            if self._paused:
                await asyncio.sleep(1)
                if live:
                    live.update(self._build_dashboard())
                continue

            # Get agents for this cycle (warmup support)
            cycle_agents = agents
            if self.warmup_controller:
                active_count = self.warmup_controller.get_active_agent_count()
                cycle_agents = agents[:active_count]

            try:
                await self._run_cycle(cycle_agents)
            except Exception as e:
                error_msg = f"Cycle error: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self._log_error_to_file(error_msg)
                self.stats.errors += 1
                self.stats.last_error = f"Cycle: {str(e)}"[:100]

            # Commit after each cycle (for sequential mode)
            if not self.parallel_mode:
                self.db.commit()

            # Advance warmup
            if self.warmup_controller:
                self.warmup_controller.advance()

            # Save checkpoint if needed
            if self.checkpoint_manager and self.checkpoint_manager.should_save(self.stats.cycles_completed):
                try:
                    self.checkpoint_manager.save(self, self.stats.cycles_completed)
                except Exception as e:
                    logger.error(f"Failed to save checkpoint: {e}")

            # Update dashboard
            if live:
                live.update(self._build_dashboard())

            # Calculate how long this cycle took (including all overhead)
            cycle_duration = time.time() - cycle_start_time

            # Sleep only for the remaining time to hit target interval
            sleep_time = max(0, interval_seconds - cycle_duration)

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # Cycle took longer than target interval
                logger.warning(
                    f"Cycle {self.stats.cycles_completed} took {cycle_duration:.1f}s, "
                    f"exceeds target interval {interval_seconds:.1f}s "
                    f"(running {-sleep_time:.1f}s behind schedule)"
                )

    async def _run_cycle(self, agents: List[Dict[str, Any]]):
        """Execute one simulation cycle."""
        # Check for stop request before starting cycle
        if self._stop_requested:
            logger.info("Stop requested, aborting cycle")
            return

        # 1. Process offers/agents for this cycle
        # Note: Wall clock time + time_scale multiplication in now() handles time advancement.
        # Each cycle sleeps for 3600/time_scale seconds, which naturally advances
        # simulated time by 1 hour when now() multiplies elapsed time by time_scale.
        # We pass hours=0 to avoid double-counting (advance_time + wall clock).
        advance_result = self.scheduler.advance_simulation_time(
            hours=0,  # No manual time advancement - wall clock handles it
            agent_ids=self.agent_ids,
            process_all_agents=self.process_all_agents,
        )
        self.stats.cycles_completed += 1
        self.stats.offers_assigned += advance_result.offers_assigned

        # 2. Get current simulated datetime
        sim_datetime = self.scheduler.time_service.now()
        sim_date = sim_datetime.date()
        self.stats.simulated_datetime = sim_datetime

        # Handle case where sim_datetime might be None
        if sim_datetime is None:
            logger.warning("No simulated datetime available, skipping agent processing")
            return

        # Check for stop request before processing agents
        if self._stop_requested:
            logger.info("Stop requested, skipping agent processing")
            return

        # 3. Process agents (parallel or sequential)
        if self.parallel_mode and self.parallel_executor:
            # PARALLEL EXECUTION
            cycle_result = await self.parallel_executor.execute_cycle(
                agents=agents,
                sim_date=sim_date,
                store_id=self.default_store_id,
                cycle_number=self.stats.cycles_completed,
            )

            # Update stats from cycle result
            self.stats.agents_processed += cycle_result.agents_processed
            self.stats.agents_shopped += cycle_result.agents_shopped
            self.stats.sessions_created += cycle_result.agents_shopped
            self.stats.checkouts_completed += cycle_result.checkouts_completed
            self.stats.checkouts_abandoned += cycle_result.checkouts_abandoned
            self.stats.events_created += cycle_result.events_created
            self.stats.errors += cycle_result.errors

            if cycle_result.errors > 0:
                self.stats.last_error = f"Cycle {self.stats.cycles_completed}: {cycle_result.errors} errors"

            # Log progress
            logger.info(
                f"Cycle {self.stats.cycles_completed}: "
                f"date={sim_date}, "
                f"agents={cycle_result.agents_processed}, "
                f"shopped={cycle_result.agents_shopped}, "
                f"checkouts={cycle_result.checkouts_completed}, "
                f"duration={cycle_result.duration_seconds:.2f}s"
            )
        else:
            # SEQUENTIAL EXECUTION (legacy mode)
            for agent in agents:
                # Check for stop request on every agent (immediate abort)
                if self._stop_requested:
                    logger.info(f"Stop requested, aborting cycle after {self.stats.agents_processed} agents")
                    return

                self.stats.agents_processed += 1

                try:
                    result = await self._run_agent(agent, sim_date)

                    if result.get("should_shop"):
                        self.stats.agents_shopped += 1
                        self.stats.sessions_created += 1
                        self.stats.events_created += result.get("events_created", 0)

                        if result.get("checkout_decision") == "complete":
                            self.stats.checkouts_completed += 1
                        elif result.get("checkout_decision") == "abandon":
                            self.stats.checkouts_abandoned += 1

                except Exception as e:
                    agent_id = agent.get("agent_id", "unknown")
                    error_msg = (
                        f"Agent {agent_id} error: {str(e)}\n{traceback.format_exc()}"
                    )
                    logger.error(error_msg)
                    self._log_error_to_file(error_msg)
                    self.stats.errors += 1
                    self.stats.last_error = f"Agent {agent_id[:15]}: {str(e)}"[:100]

            # Log progress (sequential mode)
            logger.info(
                f"Cycle {self.stats.cycles_completed}: "
                f"date={sim_date}, "
                f"sessions={self.stats.sessions_created}, "
                f"checkouts={self.stats.checkouts_completed}"
            )

    async def _run_agent(self, agent: Dict[str, Any], sim_date: date) -> Dict[str, Any]:
        """
        Run a single agent through the shopping graph.

        Args:
            agent: Agent record from database
            sim_date: Current simulated date

        Returns:
            Final state dictionary
        """
        # Create initial state
        initial_state = create_initial_state(
            agent=agent,
            simulated_date=sim_date,
            store_id=self.default_store_id,
            db=self.db,
        )

        # Run the graph
        config = {"configurable": {"thread_id": agent.get("agent_id", "unknown")}}

        # Execute graph (sync invoke, wrapped in async)
        final_state = self.shopping_graph.invoke(initial_state, config)  # type: ignore

        return final_state

    def _load_agents(
        self, agent_ids: Optional[List[str]] = None, num_agents: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Load agents from database.

        Args:
            agent_ids: Specific agent IDs to load
            num_agents: Number of agents to randomly select (overrides agent_ids if specified)

        Returns:
            List of agent dictionaries
        """
        # If num_agents is specified, load random agents
        if num_agents is not None:
            logger.info(f"Loading {num_agents} random agents")
            result = self.db.execute(
                text("""
                SELECT * FROM agents
                WHERE is_active = true
                ORDER BY RANDOM()
                LIMIT :limit
            """),
                {"limit": num_agents}
            )
        elif agent_ids:
            logger.info(f"Loading specific agents: {agent_ids}")
            # Use IN clause with proper parameter binding for multiple IDs
            # Build parameterized query for variable number of IDs
            placeholders = ", ".join([f":id_{i}" for i in range(len(agent_ids))])
            params = {f"id_{i}": aid for i, aid in enumerate(agent_ids)}

            query = f"""
                SELECT * FROM agents
                WHERE agent_id IN ({placeholders}) AND is_active = true
            """
            result = self.db.execute(text(query), params)
        else:
            # Load all active agents (removed LIMIT 100 for 372 agent scaling)
            result = self.db.execute(
                text("""
                SELECT * FROM agents
                WHERE is_active = true
                ORDER BY agent_id
            """)
            )

        agents = []
        for row in result.fetchall():
            agents.append(dict(row._mapping))

        # Log what we found
        loaded_ids = [a.get("agent_id", "unknown") for a in agents]
        logger.info(f"Loaded {len(agents)} agents: {loaded_ids}")

        if agent_ids and len(agents) < len(agent_ids):
            missing = set(agent_ids) - set(loaded_ids)
            logger.warning(f"Some agents not found or inactive: {missing}")

        return agents

    def _get_default_store(self) -> str:
        """Get a default store ID."""
        result = self.db.execute(text("SELECT id FROM stores LIMIT 1")).fetchone()
        return str(result[0]) if result else "00000000-0000-0000-0000-000000000001"

    def _build_dashboard(self) -> Panel:
        """Build Rich dashboard panel."""
        if self.debug_mode:
            return self._build_debug_dashboard()
        else:
            return self._build_simple_dashboard()

    def _build_simple_dashboard(self) -> Panel:
        """Build simple dashboard without debug logs."""
        table = Table(title="Simulation Statistics", show_header=True)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green", justify="right", width=20)

        elapsed = self.stats.elapsed_hours()
        table.add_row("Elapsed Time", f"{elapsed:.2f}h")
        sim_time_str = (
            self.stats.simulated_datetime.strftime("%Y-%m-%d %H:%M:%S")
            if self.stats.simulated_datetime
            else "N/A"
        )
        table.add_row("Simulated Time", sim_time_str)
        table.add_row("Cycles", str(self.stats.cycles_completed))

        # Mode indicator
        mode = "Parallel" if self.parallel_mode else "Sequential"
        table.add_row("Mode", mode)

        table.add_row("─" * 18, "─" * 13)
        table.add_row("Agents Processed", str(self.stats.agents_processed))
        table.add_row("Agents Shopped", str(self.stats.agents_shopped))
        table.add_row("Sessions Created", str(self.stats.sessions_created))
        table.add_row("─" * 18, "─" * 13)
        table.add_row("Checkouts", str(self.stats.checkouts_completed))
        table.add_row("Abandoned", str(self.stats.checkouts_abandoned))
        table.add_row("Events Created", str(self.stats.events_created))
        table.add_row("Offers Assigned", str(self.stats.offers_assigned))
        table.add_row("─" * 18, "─" * 13)

        # Memory usage
        mem_stats = self.memory_monitor.get_stats()
        if mem_stats.get("available"):
            mem_style = "green" if mem_stats.get("is_safe", True) else "red"
            table.add_row("Memory (MB)", f"{mem_stats['rss_mb']:.0f}", style=mem_style)

        # Latency stats
        latency = self.latency_tracker.get_aggregate()
        if latency.count > 0:
            table.add_row("Latency p50/p95", f"{latency.p50:.0f}/{latency.p95:.0f}ms")

        # Rate limiter stats
        rate_metrics = get_rate_limiter_metrics()
        if rate_metrics.get("railway_api"):
            rm = rate_metrics["railway_api"]
            table.add_row("Rate Limit", f"{rm['refill_rate']:.0f} req/s")
            table.add_row("Requests Made", str(rm["total_acquired"]))

        # Circuit breaker
        if self.circuit_breaker:
            cb_status = self.circuit_breaker.get_status()
            if cb_status["state"] == "open":
                table.add_row("Circuit Breaker", "[red bold]OPEN[/red bold]", style="red")
            else:
                table.add_row("Circuit Breaker", "Closed", style="green")

        table.add_row("─" * 18, "─" * 13)
        table.add_row(
            "Errors",
            str(self.stats.errors),
            style="red" if self.stats.errors > 0 else "green",
        )
        if self.stats.last_error:
            table.add_row("Last Error", self.stats.last_error[:40], style="red")

        title = "[bold blue]VoiceOffers Simulation[/bold blue]"
        if self._paused:
            title = "[bold red]VoiceOffers Simulation (PAUSED)[/bold red]"

        subtitle = f"Time Scale: {self.time_scale}x | LangSmith: {'ON' if os.getenv('LANGCHAIN_TRACING_V2') else 'OFF'}"

        return Panel(table, title=title, subtitle=subtitle, border_style="blue" if not self._paused else "red")

    def _build_debug_dashboard(self) -> Panel:
        """Build dashboard with debug logs."""
        layout = Layout()
        layout.split_column(
            Layout(name="stats", ratio=3),
            Layout(name="logs", ratio=2),
        )

        # Stats table
        table = Table(title="Simulation Statistics", show_header=True, box=None)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green", justify="right", width=20)

        elapsed = self.stats.elapsed_hours()
        table.add_row("Elapsed Time", f"{elapsed:.2f}h")
        logger.debug(
            f"Building dashboard - stats.simulated_datetime: {self.stats.simulated_datetime}"
        )
        sim_time_str = (
            self.stats.simulated_datetime.strftime("%Y-%m-%d %H:%M:%S")
            if self.stats.simulated_datetime
            else "N/A"
        )
        logger.debug(f"Building dashboard - sim_time_str: {sim_time_str}")
        table.add_row("Simulated Time", sim_time_str)
        table.add_row("Cycles", str(self.stats.cycles_completed))
        table.add_row("─" * 18, "─" * 13)
        table.add_row("Agents Processed", str(self.stats.agents_processed))
        table.add_row("Agents Shopped", str(self.stats.agents_shopped))
        table.add_row("Sessions Created", str(self.stats.sessions_created))
        table.add_row("─" * 18, "─" * 13)
        table.add_row("Checkouts", str(self.stats.checkouts_completed))
        table.add_row("Abandoned", str(self.stats.checkouts_abandoned))
        table.add_row("Events Created", str(self.stats.events_created))
        table.add_row("Offers Assigned", str(self.stats.offers_assigned))
        table.add_row("─" * 18, "─" * 13)
        table.add_row(
            "Errors",
            str(self.stats.errors),
            style="red" if self.stats.errors > 0 else "green",
        )
        if self.stats.last_error:
            table.add_row("Last Error", self.stats.last_error, style="red")

        layout["stats"].update(
            Panel(table, title="[bold]Statistics[/bold]", border_style="cyan")
        )

        # Log section
        log_lines = self.log_buffer.get_lines()
        if log_lines:
            log_text = "\n".join(log_lines[-15:])  # Show last 15 lines
        else:
            log_text = "[dim]No debug logs yet...[/dim]"

        log_panel = Panel(
            Text(log_text, style="dim"),
            title="[bold]Debug Logs[/bold]",
            border_style="yellow",
            padding=(0, 1),
        )
        layout["logs"].update(log_panel)

        title = "[bold blue]VoiceOffers Simulation (Debug Mode)[/bold blue]"
        subtitle = f"Time Scale: {self.time_scale}x | Press Ctrl+C to stop"

        return Panel(layout, title=title, subtitle=subtitle, border_style="blue")


async def run_simulation(
    duration_hours: float = 6.0,
    time_scale: float = 24.0,
    agent_ids: Optional[List[str]] = None,
    num_agents: Optional[int] = None,
    show_dashboard: bool = True,
    start_date: Optional[str] = None,
    process_all_agents: bool = False,
    debug_mode: bool = False,
    log_file: Optional[str] = None,
    # Scaling parameters
    rate_limit_rps: int = 50,
    checkpoint_interval: int = 10,
    warmup_cycles: int = 0,
    parallel_mode: bool = True,
    resume: bool = False,
    resume_from: Optional[str] = None,
) -> SimulationStats:
    """
    Convenience function to run simulation.

    Args:
        duration_hours: Real hours to run
        time_scale: Time compression (24 = 1h real = 1 day simulated)
        agent_ids: Specific agents or None for all
        num_agents: Number of agents to randomly select (overrides agent_ids if both specified)
        show_dashboard: Show Rich dashboard
        start_date: Simulated start date as ISO string (YYYY-MM-DD)
        process_all_agents: If True, scheduler processes all agents. If False, only processes filtered agents
        debug_mode: Enable debug logging in dashboard
        log_file: Optional file to write logs to
        rate_limit_rps: API rate limit in requests per second
        checkpoint_interval: Cycles between checkpoint saves (0 to disable)
        warmup_cycles: Number of cycles to gradually ramp up agents
        parallel_mode: Enable parallel agent execution
        resume: Resume from latest checkpoint
        resume_from: Resume from specific checkpoint file

    Returns:
        Final SimulationStats
    """
    from dotenv import load_dotenv

    load_dotenv()

    # Setup logging
    log_level = logging.DEBUG if debug_mode else logging.INFO
    handlers = []

    # Console handler with Rich
    console_handler = RichHandler(
        console=Console(stderr=True), show_time=True, show_level=True
    )
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    # Get database URL
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Create engine and session
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        orchestrator = SimulationOrchestrator(
            db=db,
            time_scale=time_scale,
            process_all_agents=process_all_agents,
            debug_mode=debug_mode,
            rate_limit_rps=rate_limit_rps,
            checkpoint_interval=checkpoint_interval,
            warmup_cycles=warmup_cycles,
            parallel_mode=parallel_mode,
            db_url=db_url,
        )

        # Handle resume
        if resume or resume_from:
            if orchestrator.checkpoint_manager:
                if resume_from:
                    checkpoint_path = Path(resume_from)
                else:
                    checkpoint_path = orchestrator.checkpoint_manager.find_latest()

                if checkpoint_path and checkpoint_path.exists():
                    orchestrator.checkpoint_manager.resume(checkpoint_path, orchestrator)
                    logger.info(f"Resumed from checkpoint: {checkpoint_path}")
                else:
                    logger.warning("No checkpoint found to resume from, starting fresh")

        # Parse start_date string to date object
        parsed_start_date = None
        if start_date:
            parsed_start_date = date.fromisoformat(start_date)

        return await orchestrator.run(
            duration_hours=duration_hours,
            agent_ids=agent_ids,
            num_agents=num_agents,
            show_dashboard=show_dashboard,
            start_date=parsed_start_date,
        )
    finally:
        # Cleanup parallel executor if used
        if hasattr(orchestrator, 'parallel_executor') and orchestrator.parallel_executor:
            orchestrator.parallel_executor.shutdown()
        db.close()


if __name__ == "__main__":
    # CLI entry point
    import argparse

    parser = argparse.ArgumentParser(
        description="Run VoiceOffers simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run 1 hour simulation with debug logs visible
  python -m app.simulation.orchestrator --hours 1 --debug

  # Run with logs saved to file
  python -m app.simulation.orchestrator --hours 6 --log-file sim.log

  # Run without dashboard (logs to console)
  python -m app.simulation.orchestrator --hours 6 --no-dashboard

  # Run 372 agents in parallel with rate limiting
  python -m app.simulation.orchestrator --hours 6 --time-scale 48 --rate-limit 50

  # Resume from latest checkpoint
  python -m app.simulation.orchestrator --resume

  # Run with warmup (gradually increase agents)
  python -m app.simulation.orchestrator --hours 6 --warmup-cycles 10
        """,
    )
    parser.add_argument(
        "--hours", type=float, default=6.0, help="Duration in real hours (default: 6.0)"
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=24.0,
        help="Time compression (default: 24.0 = 1h real = 1 day simulated)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Simulated start date (YYYY-MM-DD, default: 2024-01-01)",
    )
    parser.add_argument(
        "--agents", nargs="*", help="Specific agent IDs (e.g., agent_001 agent_002)"
    )
    parser.add_argument(
        "--num-agents",
        type=int,
        default=None,
        help="Number of agents to randomly select (e.g., 50). Overrides --agents if both specified.",
    )
    parser.add_argument(
        "--no-dashboard", action="store_true", help="Disable Rich dashboard"
    )
    parser.add_argument(
        "--process-all-agents",
        action="store_true",
        help="Process all agents in scheduler (default: only process filtered agents)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode - shows debug logs in dashboard",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Write all logs to specified file (e.g., simulation.log)",
    )
    # Scaling arguments
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=50,
        help="API rate limit in requests per second (default: 50)",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Cycles between checkpoint saves (default: 10, 0 to disable)",
    )
    parser.add_argument(
        "--warmup-cycles",
        type=int,
        default=0,
        help="Number of cycles to gradually ramp up agents (default: 0)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Use sequential execution instead of parallel (for debugging)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from latest checkpoint",
    )
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume from specific checkpoint file",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start fresh, ignore any checkpoints",
    )

    args = parser.parse_args()

    # Run
    asyncio.run(
        run_simulation(
            duration_hours=args.hours,
            time_scale=args.time_scale,
            agent_ids=args.agents,
            num_agents=args.num_agents,
            show_dashboard=not args.no_dashboard,
            start_date=args.start_date,
            process_all_agents=args.process_all_agents,
            debug_mode=args.debug,
            log_file=args.log_file,
            rate_limit_rps=args.rate_limit,
            checkpoint_interval=args.checkpoint_interval,
            warmup_cycles=args.warmup_cycles,
            parallel_mode=not args.sequential,
            resume=args.resume,
            resume_from=args.resume_from,
        )
    )
