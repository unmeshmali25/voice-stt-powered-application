"""
Real-time LLM metrics dashboard for simulation monitoring.

Integrates with the orchestrator's dashboard to display:
- Concurrent LLM calls per provider
- Latency statistics
- Cache performance
- Decision distribution
- Queue depth

Usage:
    from app.simulation.metrics.dashboard import MetricsDashboard

    dashboard = MetricsDashboard(metrics_collector)
    dashboard.start()
    # ... simulation runs ...
    dashboard.stop()
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align

from app.simulation.metrics.llm_metrics import LLMMetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """Configuration for the metrics dashboard."""

    update_interval_seconds: float = 5.0
    show_llm_section: bool = True
    show_cache_section: bool = True
    llm_percentage: float = 0.0  # 0.0 to 1.0


class MetricsDashboard:
    """
    Real-time dashboard for LLM metrics.

    Displays live metrics from the LLMMetricsCollector in a Rich console layout.
    Can be integrated with the orchestrator's existing dashboard or run standalone.

    Attributes:
        metrics_collector: Source of LLM metrics
        config: Dashboard configuration
        _live: Rich Live display instance
        _console: Rich console for output
    """

    def __init__(
        self,
        metrics_collector: LLMMetricsCollector,
        config: Optional[DashboardConfig] = None,
        console: Optional[Console] = None,
    ):
        """
        Initialize the dashboard.

        Args:
            metrics_collector: The metrics collector to display data from
            config: Dashboard configuration options
            console: Optional Rich console instance (creates one if not provided)
        """
        self.metrics_collector = metrics_collector
        self.config = config or DashboardConfig()
        self._console = console or Console()
        self._live: Optional[Live] = None
        self._start_time = time.time()

    def _build_llm_metrics_table(self) -> Table:
        """Build the LLM metrics table."""
        summary = self.metrics_collector.get_realtime_summary()
        providers = summary.get("providers", {})
        decisions = summary.get("decisions", {})

        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Provider", style="cyan", width=12)
        table.add_column("Concurrent", style="green", justify="right", width=10)
        table.add_column("Queue", style="yellow", justify="right", width=8)
        table.add_column("Latency p50", style="blue", justify="right", width=12)
        table.add_column("Latency p95", style="blue", justify="right", width=12)
        table.add_column("Errors", style="red", justify="right", width=8)

        # Ollama row
        ollama = providers.get("ollama", {})
        if ollama:
            lat = ollama.get("latency", {})
            table.add_row(
                "Ollama",
                f"{ollama.get('current_concurrent', 0)}/{ollama.get('max_concurrent', 0)}",
                str(ollama.get("queue_depth", 0)),
                f"{lat.get('p50', 0) * 1000:.0f}ms" if lat else "N/A",
                f"{lat.get('p95', 0) * 1000:.0f}ms" if lat else "N/A",
                str(ollama.get("error_count", 0)),
            )
        else:
            table.add_row("Ollama", "0/0", "0", "N/A", "N/A", "0")

        # OpenRouter row
        openrouter = providers.get("openrouter", {})
        if openrouter:
            lat = openrouter.get("latency", {})
            table.add_row(
                "OpenRouter",
                f"{openrouter.get('current_concurrent', 0)}/{openrouter.get('max_concurrent', 0)}",
                str(openrouter.get("queue_depth", 0)),
                f"{lat.get('p50', 0) * 1000:.0f}ms" if lat else "N/A",
                f"{lat.get('p95', 0) * 1000:.0f}ms" if lat else "N/A",
                str(openrouter.get("error_count", 0)),
            )
        else:
            table.add_row("OpenRouter", "0/0", "0", "N/A", "N/A", "0")

        # Decision summary row
        total = decisions.get("total_decisions", 0)
        llm = decisions.get("llm_decisions", 0)
        prob = decisions.get("probability_decisions", 0)
        llm_pct = decisions.get("llm_percentage_formatted", "0.0%")

        if total > 0:
            table.add_row(
                "[bold]Decisions[/bold]",
                f"{llm}/{prob}",
                "",
                llm_pct,
                "",
                "",
                style="dim",
            )

        return table

    def _build_cache_metrics_table(self) -> Table:
        """Build the cache metrics table."""
        summary = self.metrics_collector.get_realtime_summary()
        cache = summary.get("cache", {})

        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan", width=15)
        table.add_column("Value", style="green", justify="right", width=15)

        hits = cache.get("hits", 0)
        misses = cache.get("misses", 0)
        total = cache.get("total_lookups", 0)
        hit_rate = cache.get("hit_rate_percent", "0.0%")

        table.add_row("Hit Rate", hit_rate)
        table.add_row("Hits", str(hits))
        table.add_row("Misses", str(misses))
        table.add_row("Total Lookups", str(total))

        evictions = cache.get("evictions", 0)
        if evictions > 0:
            table.add_row("Evictions", str(evictions), style="yellow")

        return table

    def _build_summary_text(self) -> Text:
        """Build the summary text showing uptime and LLM percentage."""
        summary = self.metrics_collector.get_realtime_summary()
        uptime = summary.get("uptime_formatted", "0h 0m 0s")

        lines = [
            f"Uptime: {uptime}",
        ]

        if self.config.llm_percentage > 0:
            lines.append(f"LLM Mode: {self.config.llm_percentage * 100:.0f}% of agents")

        return Text("\n".join(lines), style="dim")

    def build_dashboard_panel(self) -> Panel:
        """
        Build the complete dashboard panel.

        Returns:
            A Rich Panel containing all LLM metrics sections
        """
        layout = Layout()

        if self.config.show_llm_section and self.config.llm_percentage > 0:
            # Split into LLM metrics and cache metrics
            layout.split_row(
                Layout(name="llm", ratio=3),
                Layout(name="cache", ratio=1),
            )

            # LLM metrics panel
            llm_table = self._build_llm_metrics_table()
            llm_panel = Panel(
                llm_table,
                title="[bold cyan]LLM Metrics[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )
            layout["llm"].update(llm_panel)

            # Cache metrics panel (if enabled)
            if self.config.show_cache_section:
                cache_table = self._build_cache_metrics_table()
                cache_panel = Panel(
                    cache_table,
                    title="[bold cyan]Cache[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
                layout["cache"].update(cache_panel)
            else:
                layout["cache"].update(Panel("[dim]Cache metrics disabled[/dim]"))

        elif self.config.show_cache_section:
            # Only show cache metrics
            cache_table = self._build_cache_metrics_table()
            layout.update(
                Panel(
                    cache_table,
                    title="[bold cyan]Decision Cache Metrics[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        else:
            # Both disabled
            layout.update(
                Panel(
                    "[dim]LLM metrics disabled (set llm_percentage > 0 to enable)[/dim]",
                    title="[bold cyan]LLM Metrics[/bold cyan]",
                    border_style="dim",
                )
            )

        # Wrap in outer panel with summary
        summary_text = self._build_summary_text()

        outer_layout = Layout()
        outer_layout.split_column(
            Layout(name="content", ratio=4),
            Layout(name="summary", ratio=1),
        )
        outer_layout["content"].update(layout)
        outer_layout["summary"].update(
            Panel(summary_text, border_style="dim", padding=(0, 1))
        )

        return Panel(
            outer_layout,
            title="[bold blue]LLM Decision Metrics[/bold blue]",
            border_style="blue",
        )

    def start(self) -> None:
        """Start the live dashboard display."""
        if self._live is not None:
            logger.warning("Dashboard already started")
            return

        self._live = Live(
            self.build_dashboard_panel(),
            refresh_per_second=0.2,  # Update every 5 seconds
            console=self._console,
        )
        self._live.start()
        logger.info("LLM metrics dashboard started")

    def stop(self) -> None:
        """Stop the live dashboard display."""
        if self._live is None:
            return

        self._live.stop()
        self._live = None
        logger.info("LLM metrics dashboard stopped")

    def update(self) -> None:
        """Update the dashboard display (call periodically)."""
        if self._live is not None:
            self._live.update(self.build_dashboard_panel())

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot without display.

        Returns:
            Dictionary with all current metrics
        """
        return self.metrics_collector.get_realtime_summary()


def create_llm_dashboard(
    metrics_collector: Optional[LLMMetricsCollector] = None,
    llm_percentage: float = 0.0,
    console: Optional[Console] = None,
) -> MetricsDashboard:
    """
    Factory function to create a metrics dashboard.

    Args:
        metrics_collector: Metrics collector (uses global if None)
        llm_percentage: Percentage of agents using LLM (for display)
        console: Optional Rich console

    Returns:
        Configured MetricsDashboard instance
    """
    from app.simulation.metrics.llm_metrics import get_metrics_collector

    if metrics_collector is None:
        metrics_collector = get_metrics_collector()

    config = DashboardConfig(
        llm_percentage=llm_percentage,
        show_llm_section=llm_percentage > 0,
        show_cache_section=True,
    )

    return MetricsDashboard(
        metrics_collector=metrics_collector,
        config=config,
        console=console,
    )
