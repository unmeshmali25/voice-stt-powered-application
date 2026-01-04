"""
Simulation Orchestrator - Coordinates time advancement and agent execution.

This module provides:
- SimulationOrchestrator: Main coordinator class
- Rich terminal dashboard for monitoring
- Integration with LangGraph agents and offer engine
"""

import asyncio
import time
import logging
import os
import sys
import signal
import traceback
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from io import StringIO
from pathlib import Path

from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session, sessionmaker
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.logging import RichHandler
from rich.progress import Progress, BarColumn, TaskProgressColumn, TimeRemainingColumn

from app.offer_engine import get_scheduler, get_config, reset_singletons
from app.simulation.agent.state import AgentState, create_initial_state
from app.simulation.agent.actions import set_actions, get_actions
from app.simulation.agent.shopping_graph import get_shopping_graph

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


@dataclass
class SimulationCheckpoint:
    """Checkpoint data structure."""

    timestamp: float
    cycle: int
    agents_completed: List[str]
    agents_in_progress: List[str]
    stats: Dict[str, Any]
    simulated_datetime: Optional[str] = None


class CheckpointManager:
    """Manages simulation checkpoints for resumability."""

    def __init__(
        self,
        checkpoint_interval_seconds: int = 300,
        checkpoint_dir: str = "data/checkpoints",
    ):
        """
        Args:
            checkpoint_interval_seconds: Save checkpoint every N seconds (default: 5 min)
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_interval_seconds = checkpoint_interval_seconds
        self.last_checkpoint_time: float = 0
        self.checkpoint_path: Path = Path(checkpoint_dir)
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

        self.last_checkpoint_time = checkpoint.timestamp
        self._cleanup_old_checkpoints(keep=10)

        return checkpoint_file

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
            try:
                old_checkpoint.unlink()
            except Exception:
                pass


class SimulationOrchestrator:
    """
    Main simulation coordinator.

    Manages:
    - Time advancement via OfferScheduler
    - Agent execution via LangGraph (concurrent via asyncio.gather)
    - Statistics tracking
    - Rich terminal dashboard
    - Database connection pooling (50 base + 10 overflow)
    - Checkpointing for resumability (every 5 min)
    - Adaptive concurrency based on system load
    """

    def __init__(
        self,
        db: Session,
        time_scale: float = 24.0,
        default_store_id: Optional[str] = None,
        process_all_agents: bool = True,
        debug_mode: bool = False,
        max_concurrent: int = 50,
        checkpoint_interval_seconds: int = 300,
        adaptive_concurrency: bool = True,
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
            max_concurrent: Maximum number of agents to run concurrently (default: 50)
            checkpoint_interval_seconds: Checkpoint interval in seconds (default: 300 = 5 min)
            adaptive_concurrency: Enable adaptive concurrency based on system load (default: True)
        """
        self.db = db
        self.time_scale = time_scale
        self.default_store_id = default_store_id or self._get_default_store()
        self.process_all_agents = process_all_agents
        self.debug_mode = debug_mode
        self.max_concurrent = max_concurrent
        self.checkpoint_interval_seconds = checkpoint_interval_seconds
        self.adaptive_concurrency = adaptive_concurrency

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

        # Initialize actions
        set_actions(db)

        # Get shopping graph
        self.shopping_graph = get_shopping_graph()

        # Stats
        self.stats = SimulationStats()

        # Rich console
        self.console = Console()

        # Control flag
        self._stop_requested = False

        # Agent filtering
        self.agent_ids: Optional[List[str]] = None

        # Error log file
        self._error_log_path = "simulation_errors.log"
        self._clear_error_log()

        # Log buffer for debug mode
        self.log_buffer = LogBuffer(max_lines=20)
        if debug_mode:
            self._setup_debug_logging()

        # Checkpoint manager
        self.checkpoint_manager = CheckpointManager(
            checkpoint_interval_seconds=checkpoint_interval_seconds
        )

        # Performance tracking
        self.agent_latencies: List[float] = []
        self.cycle_start_time: float = 0

    def _setup_debug_logging(self):
        """Setup debug logging to capture to buffer."""
        self.log_buffer.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        self.log_buffer.setFormatter(formatter)
        logging.getLogger().addHandler(self.log_buffer)

    def request_stop(self):
        """Request graceful stop of simulation."""
        self._stop_requested = True
        logger.info("Stop requested, will complete current cycle...")

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
        show_dashboard: bool = True,
        start_date: Optional[date] = None,
        resume_from_checkpoint: bool = False,
    ) -> SimulationStats:
        """
        Run simulation for specified duration.

        Args:
            duration_hours: Real-time hours to run
            agent_ids: Specific agent IDs to run, or None for all active
            show_dashboard: Show Rich terminal dashboard
            start_date: Simulated calendar start date (default: 2024-01-01)
            resume_from_checkpoint: Resume from latest checkpoint (default: False)

        Returns:
            Final SimulationStats
        """
        logger.info(f"Starting simulation: {duration_hours}h at {self.time_scale}x")

        # Store agent IDs for scheduler filtering
        self.agent_ids = agent_ids

        # Load agents
        agents = self._load_agents(agent_ids)
        logger.info(f"Loaded {len(agents)} agents")

        if not agents:
            logger.error("No agents found!")
            return self.stats

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
        else:
            logger.warning(
                "Simulation already active, skipping start_simulation() call"
            )

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
                        agents,
                        target_end_time,
                        advance_interval_seconds,
                        live,
                        resume_from_checkpoint,
                    )
                finally:
                    self._cleanup_signal_handlers()
        else:
            self._setup_signal_handlers()
            try:
                await self._run_loop(
                    agents,
                    target_end_time,
                    advance_interval_seconds,
                    None,
                    resume_from_checkpoint,
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
                self.console.print("\n[yellow]Stopping simulation...[/yellow]")
                self.request_stop()
            elif signum == signal.SIGTSTP:
                self.console.print("\n[yellow]Pausing simulation (Ctrl+Z)[/yellow]")
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
        resume_from_checkpoint: bool = False,
    ):
        """Main simulation loop."""
        # Check for existing checkpoint
        if resume_from_checkpoint:
            if checkpoint := self.checkpoint_manager.load_latest_checkpoint():
                self.console.print(
                    f"[yellow]Resuming from checkpoint at cycle {checkpoint.cycle}[/yellow]"
                )
                self.stats.cycles_completed = checkpoint.cycle
                self.stats.simulated_datetime = (
                    datetime.fromisoformat(checkpoint.simulated_datetime)
                    if checkpoint.simulated_datetime
                    else None
                )
            else:
                self.console.print(
                    "[yellow]No checkpoint found, starting fresh[/yellow]"
                )

        while time.time() < target_end_time and not self._stop_requested:
            current_time = time.time()
            self.cycle_start_time = current_time

            try:
                # Use concurrent execution if max_concurrent > 1
                if self.max_concurrent > 1:
                    await self._run_cycle_concurrent(agents)
                else:
                    await self._run_cycle(agents)

                # Track cycle time
                cycle_time = time.time() - self.cycle_start_time
                logger.debug(
                    f"Cycle {self.stats.cycles_completed} completed in {cycle_time:.2f}s"
                )

            except Exception as e:
                error_msg = f"Cycle error: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self._log_error_to_file(error_msg)
                self.stats.errors += 1
                self.stats.last_error = f"Cycle: {str(e)}"[:100]

                # Save emergency checkpoint on error
                try:
                    self._save_checkpoint(agents, is_emergency=True)
                except Exception as checkpoint_err:
                    logger.error(
                        f"Failed to save emergency checkpoint: {checkpoint_err}"
                    )

                raise

            # Commit after each cycle
            self.db.commit()

            # Checkpoint if needed
            if self.checkpoint_manager.should_checkpoint(current_time):
                try:
                    checkpoint_file = self._save_checkpoint(agents)
                    self.console.print(
                        f"[green]Checkpoint saved: {checkpoint_file.name}[/green]"
                    )
                except Exception as checkpoint_err:
                    logger.error(f"Failed to save checkpoint: {checkpoint_err}")

            # Update dashboard
            if live:
                live.update(self._build_dashboard())

            # Sleep until next cycle
            await asyncio.sleep(interval_seconds)

    async def _run_cycle(self, agents: List[Dict[str, Any]]):
        """Execute one simulation cycle."""
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

        # 3. Process each agent
        for agent in agents:
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

        # 4. Log progress
        logger.info(
            f"Cycle {self.stats.cycles_completed}: "
            f"date={sim_date}, "
            f"sessions={self.stats.sessions_created}, "
            f"checkouts={self.stats.checkouts_completed}"
        )

    async def _run_cycle_concurrent(self, agents: List[Dict[str, Any]]):
        """
        Execute agents concurrently with limited concurrency.

        Args:
            agents: List of agent dictionaries
        """
        # Determine concurrency level (adaptive if enabled)
        max_concurrent = self._get_adaptive_concurrency()

        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_agent_with_semaphore(agent: Dict[str, Any]):
            """Run single agent with semaphore and latency tracking."""
            async with semaphore:
                agent_start = time.time()
                try:
                    sim_date = (
                        self.stats.simulated_datetime.date()
                        if self.stats.simulated_datetime
                        else date.today()
                    )
                    result = await self._run_agent(agent, sim_date)
                    latency = time.time() - agent_start
                    self.agent_latencies.append(latency)
                    return agent, result, None
                except Exception as e:
                    latency = time.time() - agent_start
                    self.agent_latencies.append(latency)
                    return agent, None, e

        # Execute all agents concurrently (up to max_concurrent at once)
        tasks = [run_agent_with_semaphore(agent) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for item in results:
            # Handle exceptions from asyncio.gather (not our wrapped exceptions)
            if not isinstance(item, tuple):
                logger.error(f"Unexpected result type: {type(item)}")
                self.stats.errors += 1
                continue

            # Unpack the result tuple (agent, result, error)
            agent, result, error = item

            self.stats.agents_processed += 1

            if error:
                agent_id = agent.get("agent_id", "unknown")
                error_msg = f"Agent {agent_id} error: {str(error)}"
                logger.error(error_msg)
                self._log_error_to_file(f"{error_msg}\n{traceback.format_exc()}")
                self.stats.errors += 1
                self.stats.last_error = f"Agent {agent_id[:15]}: {str(error)}"[:100]
            elif result and result.get("should_shop"):
                self.stats.agents_shopped += 1
                self.stats.sessions_created += 1
                self.stats.events_created += result.get("events_created", 0)

                if result.get("checkout_decision") == "complete":
                    self.stats.checkouts_completed += 1
                elif result.get("checkout_decision") == "abandon":
                    self.stats.checkouts_abandoned += 1

        # Clear latency tracking for next cycle
        self.agent_latencies.clear()

    def _get_adaptive_concurrency(self) -> int:
        """
        Get current concurrency based on system load.

        Returns:
            Concurrency level between min and max bounds
        """
        if not self.adaptive_concurrency:
            return self.max_concurrent

        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem_percent = psutil.virtual_memory().percent

            min_concurrency = max(20, self.max_concurrent // 2)
            max_allowed = min(100, self.max_concurrent * 2)

            # Reduce concurrency if high load
            if cpu_percent > 80 or mem_percent > 80:
                return max(min_concurrency, self.max_concurrent // 2)

            # Increase concurrency if low load
            if cpu_percent < 50 and mem_percent < 50:
                return min(max_allowed, self.max_concurrent)

            return self.max_concurrent
        except Exception:
            # Fallback if psutil not available
            return self.max_concurrent

    def _save_checkpoint(
        self, agents: List[Dict[str, Any]], is_emergency: bool = False
    ) -> Path:
        """
        Save current simulation state to checkpoint.

        Args:
            agents: List of all agents
            is_emergency: If True, this is an emergency checkpoint

        Returns:
            Path to checkpoint file
        """
        checkpoint = SimulationCheckpoint(
            timestamp=time.time(),
            cycle=self.stats.cycles_completed,
            agents_completed=[a.get("agent_id", "unknown") for a in agents[:100]],
            agents_in_progress=[],
            stats=self.stats.to_dict(),
            simulated_datetime=(
                self.stats.simulated_datetime.isoformat()
                if self.stats.simulated_datetime
                else None
            ),
        )

        return self.checkpoint_manager.save_checkpoint(checkpoint)

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
        self, agent_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Load agents from database."""
        if agent_ids:
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
            # Remove LIMIT to allow loading all 372 agents
            result = self.db.execute(
                text("""
                SELECT * FROM agents
                WHERE is_active = true
            """)
            )

        agents = []
        for row in result.fetchall():
            agents.append(dict(row._mapping))

        # Log what we found
        loaded_ids = [a.get("agent_id", "unknown") for a in agents]
        logger.info(f"Loaded {len(agents)} agents")

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

        title = "[bold blue]VoiceOffers Simulation[/bold blue]"
        subtitle = f"Time Scale: {self.time_scale}x | LangSmith: {'ON' if os.getenv('LANGCHAIN_TRACING_V2') else 'OFF'}"

        return Panel(table, title=title, subtitle=subtitle, border_style="blue")

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
    show_dashboard: bool = True,
    start_date: Optional[str] = None,
    process_all_agents: bool = False,
    debug_mode: bool = False,
    log_file: Optional[str] = None,
    max_concurrent: int = 50,
    checkpoint_interval: int = 300,
    adaptive_concurrency: bool = True,
    resume_from_checkpoint: bool = False,
) -> SimulationStats:
    """
    Convenience function to run simulation.

    Args:
        duration_hours: Real hours to run
        time_scale: Time compression (24 = 1h real = 1 day simulated)
        agent_ids: Specific agents or None for all
        show_dashboard: Show Rich dashboard
        start_date: Simulated start date as ISO string (YYYY-MM-DD)
        process_all_agents: If True, scheduler processes all agents. If False, only processes filtered agents
        debug_mode: Enable debug logging in dashboard
        log_file: Optional file to write logs to
        max_concurrent: Max concurrent agents (default: 50)
        checkpoint_interval: Checkpoint interval in seconds (default: 300 = 5 min)
        adaptive_concurrency: Enable adaptive concurrency (default: True)
        resume_from_checkpoint: Resume from latest checkpoint (default: False)

    Returns:
        Final SimulationStats
    """
    from dotenv import load_dotenv

    # Load from .env.production if it exists, otherwise try .env
    env_file = ".env.production" if os.path.exists(".env.production") else ".env"
    load_dotenv(env_file)

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
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable not set. "
            "Please set DATABASE_URL in your .env file or environment."
        )

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Create engine with optimized connection pool for high concurrency
    engine = create_engine(
        db_url,
        pool_size=50,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
        pool_use_lifo=True,
        echo=False,
    )
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        orchestrator = SimulationOrchestrator(
            db=db,
            time_scale=time_scale,
            process_all_agents=process_all_agents,
            debug_mode=debug_mode,
            max_concurrent=max_concurrent,
            checkpoint_interval_seconds=checkpoint_interval,
            adaptive_concurrency=adaptive_concurrency,
        )
        # Parse start_date string to date object
        parsed_start_date = None
        if start_date:
            parsed_start_date = date.fromisoformat(start_date)

        return await orchestrator.run(
            duration_hours=duration_hours,
            agent_ids=agent_ids,
            show_dashboard=show_dashboard,
            start_date=parsed_start_date,
            resume_from_checkpoint=resume_from_checkpoint,
        )
    finally:
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
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=50,
        help="Max concurrent agents (default: 50, range: 1-100)",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=300,
        help="Checkpoint interval in seconds (default: 300 = 5 min)",
    )
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="Disable adaptive concurrency (default: enabled)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from latest checkpoint",
    )

    args = parser.parse_args()

    # Run
    asyncio.run(
        run_simulation(
            duration_hours=args.hours,
            time_scale=args.time_scale,
            agent_ids=args.agents,
            show_dashboard=not args.no_dashboard,
            start_date=args.start_date,
            process_all_agents=args.process_all_agents,
            debug_mode=args.debug,
            log_file=args.log_file,
            max_concurrent=args.max_concurrent,
            checkpoint_interval=args.checkpoint_interval,
            adaptive_concurrency=not args.no_adaptive,
            resume_from_checkpoint=args.resume,
        )
    )
