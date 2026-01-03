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
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
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
from rich.progress import Progress, BarColumn, TextColumn
from rich.logging import RichHandler

from app.offer_engine import get_scheduler, get_config, reset_singletons
from app.simulation.agent.state import AgentState, create_initial_state
from app.simulation.agent.actions import set_actions, get_actions, ShoppingActions
from app.simulation.agent.remote_actions import RemoteShoppingActions
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
    api_latency_ms: List[float] = field(default_factory=list)

    def elapsed_hours(self) -> float:
        return (time.time() - self.start_time) / 3600
    
    def avg_latency(self) -> float:
        if not self.api_latency_ms:
            return 0.0
        return sum(self.api_latency_ms[-50:]) / min(len(self.api_latency_ms), 50)

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
        use_api: bool = False,
        api_url: str = "http://localhost:8000"
    ):
        """
        Initialize orchestrator.

        Args:
            db: SQLAlchemy Session
            time_scale: Time compression ratio (24 = 1 real hour = 24 simulated hours)
            default_store_id: Default store for shopping sessions
            process_all_agents: If True, scheduler processes all agents.
            debug_mode: Enable debug logging in dashboard
            use_api: If True, use RemoteShoppingActions to hit API
            api_url: Base URL for API calls
        """
        self.db = db
        self.time_scale = time_scale
        self.default_store_id = default_store_id or self._get_default_store()
        self.process_all_agents = process_all_agents
        self.debug_mode = debug_mode
        self.use_api = use_api

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

        # Initialize actions (Local or Remote)
        if self.use_api:
            logger.info(f"Using RemoteShoppingActions targeting {api_url}")
            # We must set the global singleton so the graph nodes pick it up
            global _actions_instance
            remote_actions = RemoteShoppingActions(db, api_url)
            # Manually inject into the singleton slot in actions.py
            import app.simulation.agent.actions as actions_module
            actions_module._actions_instance = remote_actions
        else:
            logger.info("Using local direct DB ShoppingActions")
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

    def _get_latest_simulation_time(self) -> Optional[datetime]:
        """Fetch the latest simulated time from DB orders to resume from crash."""
        try:
            # Check orders first as they represent completed actions
            result = self.db.execute(
                text("SELECT MAX(created_at) FROM orders WHERE is_simulated = true")
            ).fetchone()
            if result and result[0]:
                return result[0]
            
            # Fallback to shopping sessions
            result = self.db.execute(
                text("SELECT MAX(started_at) FROM shopping_sessions WHERE is_simulated = true")
            ).fetchone()
            if result and result[0]:
                return result[0]
                
            return None
        except Exception as e:
            logger.error(f"Failed to fetch latest simulation time: {e}")
            return None

    async def run(
        self,
        duration_hours: float,
        agent_ids: Optional[List[str]] = None,
        show_dashboard: bool = True,
        start_date: Optional[date] = None,
    ) -> SimulationStats:
        """
        Run simulation for specified duration.

        Args:
            duration_hours: Real-time hours to run
            agent_ids: Specific agent IDs to run, or None for all active
            show_dashboard: Show Rich terminal dashboard
            start_date: Simulated calendar start date. If None, tries to resume from DB.

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

        # Determine start date (Resiliency)
        latest_sim_time = self._get_latest_simulation_time()
        
        if start_date:
            calendar_start = start_date
            logger.info(f"Using provided start date: {calendar_start}")
        elif latest_sim_time:
            calendar_start = latest_sim_time.date()
            logger.info(f"Resuming from DB timestamp: {latest_sim_time} (Date: {calendar_start})")
            # Advance time service to this point to avoid re-simulating past
            self.scheduler.time_service.start_simulation(calendar_start=calendar_start)
            # Force set the time in time_service if possible, or just let it flow
            # The scheduler uses relative offsets, so restarting might reset 'simulated_start_date'
            # We need to be careful. For now, we trust start_simulation sets the base.
        else:
            calendar_start = date(2024, 1, 1)
            logger.info(f"No history found, starting fresh: {calendar_start}")

        # Ensure simulation is started
        is_active = self.scheduler.time_service.is_simulation_active()
        if not is_active:
            self.scheduler.time_service.start_simulation(calendar_start=calendar_start)
        
        # Advance interval calculation
        advance_interval_seconds = 3600 / self.time_scale

        start_time = time.time()
        target_end_time = start_time + (duration_hours * 3600)

        if show_dashboard:
            with Live(
                self._build_dashboard(), refresh_per_second=4, console=self.console
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
    ):
        """Main simulation loop."""
        while time.time() < target_end_time and not self._stop_requested:
            cycle_start = time.time()
            try:
                await self._run_cycle(agents)
            except Exception as e:
                error_msg = f"Cycle error: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self._log_error_to_file(error_msg)
                self.stats.errors += 1
                self.stats.last_error = f"Cycle: {str(e)}"[:100]

            # Commit after each cycle
            self.db.commit()

            # Update dashboard
            if live:
                live.update(self._build_dashboard())

            # Sleep management for time_scale accuracy
            elapsed = time.time() - cycle_start
            sleep_time = max(0, interval_seconds - elapsed)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                logger.warning(f"Cycle took {elapsed:.2f}s, exceeding interval {interval_seconds:.2f}s (System overload?)")

    async def _run_cycle(self, agents: List[Dict[str, Any]]):
        """Execute one simulation cycle with batched concurrency."""
        # 1. Advance Time
        advance_result = self.scheduler.advance_simulation_time(
            hours=0,
            agent_ids=self.agent_ids,
            process_all_agents=self.process_all_agents,
        )
        self.stats.cycles_completed += 1
        self.stats.offers_assigned += advance_result.offers_assigned

        # 2. Get current simulated datetime
        sim_datetime = self.scheduler.time_service.now()
        sim_date = sim_datetime.date()
        self.stats.simulated_datetime = sim_datetime

        if sim_datetime is None:
            logger.warning("No simulated datetime available, skipping agent processing")
            return

        # 3. Process agents in batches (Phase 2 Concurrency)
        BATCH_SIZE = 50
        
        for i in range(0, len(agents), BATCH_SIZE):
            batch = agents[i:i + BATCH_SIZE]
            tasks = []
            
            for agent in batch:
                tasks.append(self._safe_run_agent(agent, sim_date))
                
            # Run batch concurrently
            results = await asyncio.gather(*tasks)
            
            # Process results
            for result in results:
                self.stats.agents_processed += 1
                if result:
                    if result.get("should_shop"):
                        self.stats.agents_shopped += 1
                        self.stats.sessions_created += 1
                        self.stats.events_created += result.get("events_created", 0)

                        if result.get("checkout_decision") == "complete":
                            self.stats.checkouts_completed += 1
                        elif result.get("checkout_decision") == "abandon":
                            self.stats.checkouts_abandoned += 1
            
            # Commit mid-cycle to free up connections/locks if using direct DB
            if not self.use_api:
                self.db.commit()

        # 4. Log progress
        logger.info(
            f"Cycle {self.stats.cycles_completed}: "
            f"date={sim_date}, "
            f"sessions={self.stats.sessions_created}, "
            f"checkouts={self.stats.checkouts_completed}"
        )

    async def _safe_run_agent(self, agent: Dict[str, Any], sim_date: date) -> Optional[Dict[str, Any]]:
        """Wrapper to handle individual agent errors without crashing batch."""
        try:
            return await self._run_agent(agent, sim_date)
        except Exception as e:
            agent_id = agent.get("agent_id", "unknown")
            error_msg = f"Agent {agent_id} error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self._log_error_to_file(error_msg)
            self.stats.errors += 1
            self.stats.last_error = f"Agent {agent_id[:15]}: {str(e)}"[:100]
            return None

    async def _run_agent(self, agent: Dict[str, Any], sim_date: date) -> Dict[str, Any]:
        """Run a single agent through the shopping graph (offloaded to thread)."""
        # Offload synchronous graph execution to a thread to prevent blocking the event loop
        # This allows asyncio.gather to actually run agents concurrently
        return await asyncio.to_thread(self._run_agent_sync, agent, sim_date)

    def _run_agent_sync(self, agent: Dict[str, Any], sim_date: date) -> Dict[str, Any]:
        """Synchronous execution of the agent graph."""
        # Create initial state
        initial_state = create_initial_state(
            agent=agent,
            simulated_date=sim_date,
            store_id=self.default_store_id,
            db=self.db,
        )

        # Run the graph
        config = {"configurable": {"thread_id": agent.get("agent_id", "unknown")}}

        # Execute graph (sync invoke)
        # We use invoke() because the underlying actions are synchronous (httpx.Client)
        # and we are running inside a thread.
        final_state = self.shopping_graph.invoke(initial_state, config)

        return final_state  # type: ignore

    def _load_agents(
        self,
        agent_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Load agents from database."""
        # Increase limit for scaling
        limit = 1000 if not agent_ids else len(agent_ids)
        
        if agent_ids:
            logger.info(f"Loading specific agents: {agent_ids}")
            placeholders = ", ".join([f":id_{i}" for i in range(len(agent_ids))])
            params = {f"id_{i}": aid for i, aid in enumerate(agent_ids)}

            query = f"""
                SELECT * FROM agents
                WHERE agent_id IN ({placeholders}) AND is_active = true
            """
            result = self.db.execute(text(query), params)
        else:
            result = self.db.execute(
                text(f"""
                SELECT * FROM agents
                WHERE is_active = true
                LIMIT {limit}
            """)
            )

        agents = []
        for row in result.fetchall():
            agents.append(dict(row._mapping))

        # Log what we found
        loaded_ids = [a.get("agent_id", "unknown") for a in agents]
        logger.info(f"Loaded {len(agents)} agents.")

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
        
        # Latency metric
        latency = self.stats.avg_latency()
        if latency > 0:
            table.add_row("Avg API Latency", f"{latency:.0f}ms", style="yellow")
            
        table.add_row(
            "Errors",
            str(self.stats.errors),
            style="red" if self.stats.errors > 0 else "green",
        )
        if self.stats.last_error:
            table.add_row("Last Error", self.stats.last_error, style="red")

        title = "[bold blue]VoiceOffers Simulation[/bold blue]"
        mode = "Remote API" if self.use_api else "Local DB"
        subtitle = f"Scale: {self.time_scale}x | Mode: {mode} | Agents: {len(self.agent_ids) if self.agent_ids else 'All'}"

        return Panel(table, title=title, subtitle=subtitle, border_style="blue")

    def _build_debug_dashboard(self) -> Panel:
        """Build dashboard with debug logs."""
        layout = Layout()
        layout.split_column(
            Layout(name="stats", ratio=3),
            Layout(name="logs", ratio=2),
        )

        # Re-use simple dashboard logic for stats table part
        # But we need to construct it manually to fit in layout
        table = Table(title="Simulation Statistics", show_header=True, box=None)
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
        table.add_row("Checkouts", str(self.stats.checkouts_completed))
        table.add_row("Abandoned", str(self.stats.checkouts_abandoned))
        
        if self.use_api:
             table.add_row("Avg Latency", f"{self.stats.avg_latency():.0f}ms")

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

        title = "[bold blue]VoiceOffers Simulation (Debug)[/bold blue]"
        mode = "Remote API" if self.use_api else "Local DB"
        subtitle = f"Scale: {self.time_scale}x | Mode: {mode}"

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
    use_api: bool = False,
    api_url: str = "http://localhost:8000"
) -> SimulationStats:
    """
    Convenience function to run simulation.
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

    # Phase 4: Pooling Optimization
    # Create engine with increased pool size for concurrency
    engine = create_engine(
        db_url,
        pool_size=20,          # Increased from default 5
        max_overflow=40,       # Allow more overflow
        pool_timeout=30,
        pool_pre_ping=True
    )
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        orchestrator = SimulationOrchestrator(
            db=db,
            time_scale=time_scale,
            process_all_agents=process_all_agents,
            debug_mode=debug_mode,
            use_api=use_api,
            api_url=api_url
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
        )
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    # CLI entry point
    import argparse

    parser = argparse.ArgumentParser(
        description="Run VoiceOffers simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        help="Simulated start date (YYYY-MM-DD, default: Resume from DB)",
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
        "--api",
        action="store_true",
        help="Use API for cart/checkout instead of direct DB writes",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL for API calls (default: http://localhost:8000)",
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
            use_api=args.api,
            api_url=args.api_url
        )
    )