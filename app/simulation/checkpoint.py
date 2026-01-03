"""
Checkpoint manager for simulation state persistence.

Provides:
- Periodic checkpoint saves (every N cycles)
- Crash recovery with orphaned session cleanup
- Atomic file writes to prevent corruption
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.simulation.orchestrator import SimulationOrchestrator

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manage simulation checkpoints for crash recovery.

    Checkpoints are JSON files containing:
    - Configuration (time_scale, rate_limit, etc.)
    - State (cycle number, simulated datetime)
    - Statistics (sessions, checkouts, errors)

    Usage:
        manager = CheckpointManager(save_interval_cycles=10)

        # In simulation loop
        if manager.should_save(cycle_number):
            manager.save(orchestrator, cycle_number)

        # On restart
        if args.resume:
            checkpoint = manager.find_latest()
            if checkpoint:
                manager.resume(checkpoint, orchestrator)
    """

    def __init__(
        self,
        checkpoint_dir: Path = None,
        save_interval_cycles: int = 10,
        max_checkpoints: int = 5,
    ):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoint files (default: ./data/checkpoints)
            save_interval_cycles: Cycles between automatic saves
            max_checkpoints: Max checkpoint files to keep (oldest are deleted)
        """
        self.checkpoint_dir = Path(checkpoint_dir or "./data/checkpoints")
        self.save_interval_cycles = save_interval_cycles
        self.max_checkpoints = max_checkpoints

        # Ensure directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Checkpoint manager initialized: dir={self.checkpoint_dir}, interval={save_interval_cycles}")

    def should_save(self, cycle: int) -> bool:
        """
        Check if checkpoint should be saved this cycle.

        Args:
            cycle: Current cycle number

        Returns:
            True if checkpoint should be saved
        """
        return cycle > 0 and cycle % self.save_interval_cycles == 0

    def save(
        self,
        orchestrator: 'SimulationOrchestrator',
        cycle: int,
    ) -> Path:
        """
        Save checkpoint after cycle completes.

        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            orchestrator: The simulation orchestrator instance
            cycle: Current cycle number

        Returns:
            Path to saved checkpoint file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"checkpoint_{timestamp}_cycle_{cycle}.json"
        filepath = self.checkpoint_dir / filename

        # Build checkpoint data
        checkpoint_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "simulation_config": self._get_config(orchestrator),
            "simulation_state": self._get_state(orchestrator, cycle),
            "statistics": self._get_statistics(orchestrator),
        }

        # Atomic write: write to temp file, then rename
        temp_path = filepath.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2, default=str)
            temp_path.rename(filepath)
            logger.info(f"Checkpoint saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()

        return filepath

    def _get_config(self, orchestrator: 'SimulationOrchestrator') -> Dict[str, Any]:
        """Extract configuration from orchestrator."""
        config = {
            "time_scale": getattr(orchestrator, 'time_scale', None),
            "default_store_id": getattr(orchestrator, 'default_store_id', None),
            "process_all_agents": getattr(orchestrator, 'process_all_agents', True),
        }

        # Rate limiter config
        if hasattr(orchestrator, 'rate_limiter'):
            config["rate_limit_rps"] = orchestrator.rate_limiter.refill_rate

        # Checkpoint config
        config["checkpoint_interval"] = self.save_interval_cycles

        return config

    def _get_state(self, orchestrator: 'SimulationOrchestrator', cycle: int) -> Dict[str, Any]:
        """Extract current state from orchestrator."""
        state = {
            "current_cycle": cycle,
            "simulated_datetime": None,
        }

        if hasattr(orchestrator, 'stats') and orchestrator.stats.simulated_datetime:
            state["simulated_datetime"] = orchestrator.stats.simulated_datetime.isoformat()

        return state

    def _get_statistics(self, orchestrator: 'SimulationOrchestrator') -> Dict[str, Any]:
        """Extract statistics from orchestrator."""
        if hasattr(orchestrator, 'stats'):
            return orchestrator.stats.to_dict()
        return {}

    def find_latest(self) -> Optional[Path]:
        """
        Find most recent checkpoint file.

        Returns:
            Path to latest checkpoint, or None if no checkpoints exist
        """
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return checkpoints[0] if checkpoints else None

    def list_checkpoints(self) -> list:
        """List all available checkpoints, newest first."""
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [
            {
                "path": str(p),
                "filename": p.name,
                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "size_kb": round(p.stat().st_size / 1024, 1),
            }
            for p in checkpoints
        ]

    def load(self, filepath: Path) -> Dict[str, Any]:
        """
        Load checkpoint from file.

        Args:
            filepath: Path to checkpoint file

        Returns:
            Checkpoint data dictionary
        """
        with open(filepath) as f:
            return json.load(f)

    def resume(
        self,
        filepath: Path,
        orchestrator: 'SimulationOrchestrator',
    ) -> Dict[str, Any]:
        """
        Resume simulation from checkpoint.

        Restores:
        - Cycle number
        - Statistics

        Args:
            filepath: Path to checkpoint file
            orchestrator: Orchestrator to restore state into

        Returns:
            Loaded checkpoint data
        """
        data = self.load(filepath)

        logger.info(f"Resuming from checkpoint: {filepath}")

        # Restore statistics
        stats_data = data.get("statistics", {})
        if hasattr(orchestrator, 'stats'):
            self._restore_stats(orchestrator.stats, stats_data)

        # Log restored state
        state = data.get("simulation_state", {})
        logger.info(
            f"Restored: cycle={state.get('current_cycle', 0)}, "
            f"simulated_datetime={state.get('simulated_datetime', 'N/A')}"
        )

        # Clean up orphaned sessions from crash
        if hasattr(orchestrator, 'db'):
            orphaned = self._cleanup_orphaned_sessions(orchestrator.db)
            if orphaned > 0:
                logger.info(f"Cleaned up {orphaned} orphaned sessions from previous crash")

        return data

    def _restore_stats(self, stats, stats_data: Dict[str, Any]) -> None:
        """Restore statistics object from checkpoint data."""
        stats.cycles_completed = stats_data.get("cycles_completed", 0)
        stats.agents_processed = stats_data.get("agents_processed", 0)
        stats.agents_shopped = stats_data.get("agents_shopped", 0)
        stats.sessions_created = stats_data.get("sessions_created", 0)
        stats.checkouts_completed = stats_data.get("checkouts_completed", 0)
        stats.checkouts_abandoned = stats_data.get("checkouts_abandoned", 0)
        stats.offers_assigned = stats_data.get("offers_assigned", 0)
        stats.events_created = stats_data.get("events_created", 0)
        stats.errors = stats_data.get("errors", 0)

    def _cleanup_orphaned_sessions(self, db: Session) -> int:
        """
        Clean up sessions left in 'active' state from crash.

        Args:
            db: Database session

        Returns:
            Number of orphaned sessions cleaned up
        """
        try:
            # Mark orphaned sessions as abandoned
            result = db.execute(text("""
                UPDATE shopping_sessions
                SET status = 'abandoned',
                    ended_at = NOW(),
                    notes = 'Auto-abandoned: orphaned from simulation crash'
                WHERE status = 'active'
                  AND is_simulated = true
                RETURNING id
            """))
            orphaned = result.fetchall()
            orphaned_count = len(orphaned)

            # Clear orphaned cart items for simulation agents
            db.execute(text("""
                DELETE FROM cart_items
                WHERE user_id IN (
                    SELECT user_id FROM agents WHERE is_active = true
                )
            """))

            # Clear orphaned cart coupons for simulation agents
            db.execute(text("""
                DELETE FROM cart_coupons
                WHERE user_id IN (
                    SELECT user_id FROM agents WHERE is_active = true
                )
            """))

            db.commit()
            return orphaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned sessions: {e}")
            db.rollback()
            return 0

    def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoint files, keeping most recent."""
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for old in checkpoints[self.max_checkpoints:]:
            try:
                old.unlink()
                logger.debug(f"Removed old checkpoint: {old}")
            except Exception as e:
                logger.warning(f"Failed to remove old checkpoint {old}: {e}")

    def force_save(
        self,
        orchestrator: 'SimulationOrchestrator',
        cycle: int,
        reason: str = "manual",
    ) -> Path:
        """
        Force an immediate checkpoint save.

        Args:
            orchestrator: The simulation orchestrator
            cycle: Current cycle number
            reason: Reason for forced save (for logging)

        Returns:
            Path to saved checkpoint
        """
        logger.info(f"Forcing checkpoint save: reason={reason}")
        return self.save(orchestrator, cycle)
