"""
Run Recorder - Automatically saves simulation run summaries.

Creates a structured directory after each simulation run:
simulation_runs/
├── 2026-02-17_run_001/
│   ├── checkpoint.json
│   ├── summary.md
│   └── metadata.json
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.orchestrator import SimulationStats


class RunRecorder:
    """Records simulation runs to structured directories."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path("simulation_runs")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def record_run(
        self,
        stats: "SimulationStats",
        config: Dict[str, Any],
        checkpoint_path: Optional[Path] = None,
        performance: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Record a completed simulation run.

        Args:
            stats: SimulationStats from orchestrator
            config: Simulation configuration dict
            checkpoint_path: Path to final checkpoint file
            performance: Optional performance metrics (latency, etc.)

        Returns:
            Path to the run directory
        """
        run_dir = self._create_run_dir()
        run_id = run_dir.name

        metadata = self._build_metadata(run_id, stats, config, performance)
        with open(run_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        summary = self._build_summary(run_id, stats, config, performance)
        with open(run_dir / "summary.md", "w") as f:
            f.write(summary)

        if checkpoint_path and checkpoint_path.exists():
            shutil.copy(checkpoint_path, run_dir / "checkpoint.json")

        return run_dir

    def _create_run_dir(self) -> Path:
        """Create a new run directory with incrementing number."""
        today = datetime.now().strftime("%Y-%m-%d")
        existing = list(self.base_dir.glob(f"{today}_run_*"))
        next_num = len(existing) + 1
        run_dir = self.base_dir / f"{today}_run_{next_num:03d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _build_metadata(
        self,
        run_id: str,
        stats: "SimulationStats",
        config: Dict[str, Any],
        performance: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "simulation_config": config,
            "final_statistics": stats.to_dict(),
            "performance": performance or {},
        }

    def _build_summary(
        self,
        run_id: str,
        stats: "SimulationStats",
        config: Dict[str, Any],
        performance: Optional[Dict[str, Any]],
    ) -> str:
        perf = performance or {}
        time_scale = config.get("time_scale", 1.0)

        elapsed = stats.elapsed_hours()
        simulated_days = elapsed * time_scale / 24 if time_scale else 0

        lines = [
            f"# Simulation Run: {run_id}",
            "",
            "## Run Overview",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| **Real Duration** | {elapsed:.2f} hours |",
            f"| **Simulated Duration** | ~{simulated_days:.0f} days |",
            f"| **Time Scale** | {time_scale}x |",
            f"| **Mode** | {config.get('mode', 'unknown')} |",
            f"| **Errors** | {stats.errors} |",
            "",
            "## Performance Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| **Cycles Completed** | {stats.cycles_completed} |",
            f"| **Agents Processed** | {stats.agents_processed:,} |",
        ]

        if perf.get("latency_p50_ms"):
            lines.extend(
                [
                    f"| **Latency p50/p95** | {perf['latency_p50_ms']}ms / {perf['latency_p95_ms']}ms |",
                    f"| **Requests Made** | {perf.get('requests_total', 'N/A'):,} |",
                ]
            )

        if perf.get("circuit_breaker_state"):
            lines.append(f"| **Circuit Breaker** | {perf['circuit_breaker_state']} |")

        lines.extend(
            [
                "",
                "## Shopping Behavior",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| **Agents Shopped** | {stats.agents_shopped:,} |",
                f"| **Sessions Created** | {stats.sessions_created:,} |",
                f"| **Checkouts Completed** | {stats.checkouts_completed:,} |",
                f"| **Checkouts Abandoned** | {stats.checkouts_abandoned:,} |",
            ]
        )

        if stats.checkouts_completed + stats.checkouts_abandoned > 0:
            abandon_rate = (
                stats.checkouts_abandoned
                / (stats.checkouts_completed + stats.checkouts_abandoned)
                * 100
            )
            lines.append(f"| **Abandon Rate** | {abandon_rate:.1f}% |")

        if stats.agents_processed > 0:
            shop_rate = stats.agents_shopped / stats.agents_processed * 100
            lines.append(f"| **Shop Rate** | {shop_rate:.2f}% of processed agents |")

        lines.extend(
            [
                "",
                "## Business Metrics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| **Offers Assigned** | {stats.offers_assigned:,} |",
                f"| **Events Created** | {stats.events_created:,} |",
            ]
        )

        if stats.agents_shopped > 0:
            lines.append(
                f"| **Avg Offers per Shopper** | {stats.offers_assigned / stats.agents_shopped:.1f} |"
            )

        if stats.sessions_created > 0:
            lines.append(
                f"| **Avg Events per Session** | {stats.events_created / stats.sessions_created:.1f} |"
            )

        lines.extend(
            [
                "",
                "## Simulation Config",
                "",
                f"- **Time Scale**: {time_scale}",
                f"- **Default Store ID**: `{config.get('default_store_id', 'N/A')}`",
                f"- **Process All Agents**: {config.get('process_all_agents', 'N/A')}",
                f"- **Rate Limit**: {config.get('rate_limit_rps', 'N/A')} req/s",
                f"- **Checkpoint Interval**: {config.get('checkpoint_interval', 'N/A')} cycles",
                "",
                "## Notes",
                "",
                f"- Simulation ran with {stats.errors} error(s)",
            ]
        )

        return "\n".join(lines)


def record_simulation_run(
    stats: "SimulationStats",
    config: Dict[str, Any],
    checkpoint_path: Optional[Path] = None,
    performance: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Convenience function to record a simulation run.

    Args:
        stats: SimulationStats from orchestrator
        config: Simulation configuration dict
        checkpoint_path: Path to final checkpoint file
        performance: Optional performance metrics

    Returns:
        Path to the run directory
    """
    recorder = RunRecorder()
    return recorder.record_run(stats, config, checkpoint_path, performance)
