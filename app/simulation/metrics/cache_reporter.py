"""
Cache effectiveness reporter for post-run analysis.

Generates comprehensive reports showing the impact of caching on LLM usage,
including time savings and cost savings with provider breakdowns.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.simulation.metrics.llm_metrics import LLMMetricsCollector

logger = logging.getLogger(__name__)


# Pricing estimates per 1K tokens (approximate for OpenRouter tier models)
# Ollama is self-hosted so cost is $0
PRICING_PER_1K_TOKENS = {
    "ollama": {"input": 0.0, "output": 0.0, "per_request": 0.0},
    "openrouter": {
        "input": 0.0015,
        "output": 0.002,
        "per_request": 0.005,
    },  # ~$0.005 per request
}

# Average tokens per request (for cost estimation when exact counts unavailable)
DEFAULT_TOKENS_PER_REQUEST = {
    "input": 500,  # Prompt tokens
    "output": 100,  # Completion tokens
}


@dataclass
class ProviderSavings:
    """Savings breakdown for a single provider."""

    provider: str
    calls_saved: int = 0
    time_saved_ms: float = 0.0
    input_tokens_saved: int = 0
    output_tokens_saved: int = 0
    cost_saved: float = 0.0

    @property
    def time_saved_seconds(self) -> float:
        """Return time saved in seconds."""
        return self.time_saved_ms / 1000

    @property
    def time_saved_formatted(self) -> str:
        """Return human-readable time saved."""
        seconds = self.time_saved_seconds
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f} minutes"
        else:
            return f"{seconds / 3600:.2f} hours"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "calls_saved": self.calls_saved,
            "time_saved_ms": self.time_saved_ms,
            "time_saved_seconds": self.time_saved_seconds,
            "time_saved_formatted": self.time_saved_formatted,
            "input_tokens_saved": self.input_tokens_saved,
            "output_tokens_saved": self.output_tokens_saved,
            "cost_saved": self.cost_saved,
            "cost_saved_formatted": f"${self.cost_saved:.4f}",
        }


@dataclass
class CacheEffectivenessReport:
    """Complete cache effectiveness report."""

    # Metadata
    simulation_id: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
    report_duration_seconds: float = 0.0

    # Cache statistics
    total_cache_hits: int = 0
    total_cache_misses: int = 0
    cache_hit_rate: float = 0.0

    # Overall savings
    total_calls_saved: int = 0
    total_time_saved_ms: float = 0.0
    total_cost_saved: float = 0.0

    # Provider breakdown
    provider_savings: List[ProviderSavings] = field(default_factory=list)

    # Additional metrics
    avg_latency_ms: float = 0.0
    estimated_tokens_saved: int = 0

    @property
    def total_time_saved_formatted(self) -> str:
        """Return human-readable total time saved."""
        seconds = self.total_time_saved_ms / 1000
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds / 60:.1f} minutes ({seconds * 1000:.0f}ms)"
        else:
            hours = seconds / 3600
            return f"{hours:.2f} hours ({seconds * 1000:.0f}ms)"

    @property
    def total_cost_saved_formatted(self) -> str:
        """Return formatted cost saved."""
        return f"${self.total_cost_saved:.4f}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "metadata": {
                "simulation_id": self.simulation_id,
                "generated_at": self.generated_at.isoformat(),
                "report_duration_seconds": self.report_duration_seconds,
            },
            "cache_statistics": {
                "total_cache_hits": self.total_cache_hits,
                "total_cache_misses": self.total_cache_misses,
                "cache_hit_rate": self.cache_hit_rate,
                "cache_hit_rate_percent": f"{self.cache_hit_rate * 100:.1f}%",
            },
            "savings_summary": {
                "total_calls_saved": self.total_calls_saved,
                "total_time_saved_ms": self.total_time_saved_ms,
                "total_time_saved_formatted": self.total_time_saved_formatted,
                "total_cost_saved": self.total_cost_saved,
                "total_cost_saved_formatted": self.total_cost_saved_formatted,
                "estimated_tokens_saved": self.estimated_tokens_saved,
                "avg_latency_ms": self.avg_latency_ms,
            },
            "provider_breakdown": [ps.to_dict() for ps in self.provider_savings],
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Cache Effectiveness Report",
            "",
            f"**Simulation ID:** {self.simulation_id or 'N/A'}",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"**Report Generation Time:** {self.report_duration_seconds:.2f}s",
            "",
            "## Cache Performance",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Cache Hits | {self.total_cache_hits:,} |",
            f"| Total Cache Misses | {self.total_cache_misses:,} |",
            f"| Cache Hit Rate | {self.cache_hit_rate * 100:.1f}% |",
            "",
            "## Savings Summary",
            "",
            f"### 📊 Calls Saved",
            f"**{self.total_calls_saved:,}** LLM calls avoided through caching",
            "",
            f"### ⏱️ Time Saved",
            f"**{self.total_time_saved_formatted}**",
            f"(Average latency per call: {self.avg_latency_ms:.0f}ms)",
            "",
            f"### 💰 Cost Saved",
            f"**{self.total_cost_saved_formatted}**",
            f"(Estimated {self.estimated_tokens_saved:,} tokens saved)",
            "",
            "## Provider Breakdown",
            "",
        ]

        if self.provider_savings:
            lines.extend(
                [
                    "| Provider | Calls Saved | Time Saved | Cost Saved |",
                    "|----------|-------------|------------|------------|",
                ]
            )
            for ps in self.provider_savings:
                lines.append(
                    f"| {ps.provider.capitalize()} | {ps.calls_saved:,} | {ps.time_saved_formatted} | ${ps.cost_saved:.4f} |"
                )
        else:
            lines.append("*No provider-specific data available*")

        lines.extend(
            [
                "",
                "## Impact Analysis",
                "",
            ]
        )

        if self.total_calls_saved > 0:
            efficiency = self.cache_hit_rate * 100
            lines.extend(
                [
                    f"- **Cache Efficiency:** {efficiency:.1f}% of lookups were served from cache",
                    f"- **Performance Impact:** Saved {self.total_time_saved_formatted} of LLM latency",
                    f"- **Cost Impact:** Reduced API costs by {self.total_cost_saved_formatted}",
                ]
            )

            if self.total_cost_saved > 0:
                cost_per_call = self.total_cost_saved / self.total_calls_saved
                lines.append(f"- **Average Cost Per Saved Call:** ${cost_per_call:.6f}")
        else:
            lines.append("*No cache savings recorded in this simulation run*")

        lines.extend(
            [
                "",
                "---",
                "*Report generated by Cache Effectiveness Reporter*",
            ]
        )

        return "\n".join(lines)


class CacheEffectivenessReporter:
    """
    Generates post-run cache effectiveness reports.

    Analyzes metrics from the simulation run to calculate:
    - LLM calls saved (cache hits)
    - Time saved (based on average latency)
    - Cost saved (based on provider pricing)
    - Provider breakdown (Ollama vs OpenRouter)

    Usage:
        reporter = CacheEffectivenessReporter()

        # Generate report from metrics collector
        report = reporter.generate_report(
            metrics_collector=collector,
            simulation_id="sim_001"
        )

        # Export to file
        reporter.export_report(report, format="markdown", path="reports/cache_report.md")
    """

    def __init__(
        self,
        pricing_config: Optional[Dict[str, Dict[str, float]]] = None,
        default_tokens: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize the reporter.

        Args:
            pricing_config: Pricing per provider (input/output/per_request costs)
            default_tokens: Default token counts for estimation
        """
        self.pricing = pricing_config or PRICING_PER_1K_TOKENS
        self.default_tokens = default_tokens or DEFAULT_TOKENS_PER_REQUEST

    def generate_report(
        self,
        metrics_collector: LLMMetricsCollector,
        simulation_id: Optional[str] = None,
    ) -> CacheEffectivenessReport:
        """
        Generate a cache effectiveness report from metrics.

        Args:
            metrics_collector: The LLM metrics collector from the simulation run
            simulation_id: Optional simulation run identifier

        Returns:
            CacheEffectivenessReport with complete analysis
        """
        start_time = time.time()

        # Get cache statistics
        cache_summary = metrics_collector.get_cache_summary()
        total_hits = cache_summary.get("hits", 0)
        total_misses = cache_summary.get("misses", 0)
        hit_rate = cache_summary.get("hit_rate", 0.0)

        # Get provider metrics for latency and cost calculation
        provider_summaries = {
            "ollama": metrics_collector.get_provider_summary("ollama"),
            "openrouter": metrics_collector.get_provider_summary("openrouter"),
        }

        # Calculate overall average latency across all providers
        all_latencies = []
        for provider, summary in provider_summaries.items():
            latencies = summary.get("latency", {})
            avg_latency = latencies.get("avg", 0)
            count = latencies.get("count", 0)
            if count > 0:
                all_latencies.extend([avg_latency] * count)

        avg_latency_ms = (
            (sum(all_latencies) / len(all_latencies) * 1000) if all_latencies else 1500
        )  # Default 1.5s

        # Calculate savings per provider
        provider_savings = []
        total_time_saved_ms = 0.0
        total_cost_saved = 0.0
        total_tokens_saved = 0

        for provider, summary in provider_summaries.items():
            provider_config = self.pricing.get(provider, self.pricing["openrouter"])

            # Get call count for this provider (approximate cache hits)
            # In a real scenario, we'd track which provider's cache was hit
            # For now, distribute hits proportionally based on total calls
            provider_calls = summary.get("total_calls", 0)
            total_calls = sum(
                s.get("total_calls", 0) for s in provider_summaries.values()
            )

            if total_calls > 0:
                # Proportional distribution of cache hits
                provider_hit_ratio = provider_calls / total_calls
                provider_hits = int(total_hits * provider_hit_ratio)
            else:
                # If no calls made, assume 50/50 split
                provider_hits = (
                    total_hits // 2
                    if provider == "ollama"
                    else total_hits - (total_hits // 2)
                )

            # Get average latency for this provider
            latencies = summary.get("latency", {})
            provider_avg_latency_ms = latencies.get("avg", avg_latency_ms / 1000) * 1000

            # Calculate time saved
            time_saved_ms = provider_hits * provider_avg_latency_ms

            # Calculate token and cost savings
            input_tokens = provider_hits * self.default_tokens["input"]
            output_tokens = provider_hits * self.default_tokens["output"]

            input_cost = (input_tokens / 1000) * provider_config["input"]
            output_cost = (output_tokens / 1000) * provider_config["output"]
            request_cost = provider_hits * provider_config["per_request"]
            cost_saved = input_cost + output_cost + request_cost

            savings = ProviderSavings(
                provider=provider,
                calls_saved=provider_hits,
                time_saved_ms=time_saved_ms,
                input_tokens_saved=input_tokens,
                output_tokens_saved=output_tokens,
                cost_saved=cost_saved,
            )

            provider_savings.append(savings)
            total_time_saved_ms += time_saved_ms
            total_cost_saved += cost_saved
            total_tokens_saved += input_tokens + output_tokens

        # Create report
        report = CacheEffectivenessReport(
            simulation_id=simulation_id,
            generated_at=datetime.utcnow(),
            report_duration_seconds=time.time() - start_time,
            total_cache_hits=total_hits,
            total_cache_misses=total_misses,
            cache_hit_rate=hit_rate,
            total_calls_saved=total_hits,
            total_time_saved_ms=total_time_saved_ms,
            total_cost_saved=total_cost_saved,
            provider_savings=provider_savings,
            avg_latency_ms=avg_latency_ms,
            estimated_tokens_saved=total_tokens_saved,
        )

        logger.info(
            f"Generated cache effectiveness report in {report.report_duration_seconds:.2f}s"
        )
        return report

    def export_report(
        self,
        report: CacheEffectivenessReport,
        format: str = "markdown",
        path: Optional[str] = None,
        output_dir: str = "reports",
    ) -> str:
        """
        Export report to file.

        Args:
            report: The report to export
            format: "markdown", "json", or "both"
            path: Specific file path (optional, auto-generated if not provided)
            output_dir: Directory for auto-generated paths

        Returns:
            Path to the exported file
        """
        # Generate filename if not provided
        if path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            sim_id = report.simulation_id or "unknown"

            if format == "json":
                filename = f"cache_report_{sim_id}_{timestamp}.json"
            else:
                filename = f"cache_report_{sim_id}_{timestamp}.md"

            path = Path(output_dir) / filename

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            content = json.dumps(report.to_dict(), indent=2)
            path.write_text(content)
            logger.info(f"Exported JSON report to {path}")

        elif format == "markdown":
            content = report.to_markdown()
            path.write_text(content)
            logger.info(f"Exported Markdown report to {path}")

        elif format == "both":
            # Export both formats
            json_path = path.with_suffix(".json")
            md_path = path.with_suffix(".md")

            json_content = json.dumps(report.to_dict(), indent=2)
            json_path.write_text(json_content)
            logger.info(f"Exported JSON report to {json_path}")

            md_content = report.to_markdown()
            md_path.write_text(md_content)
            logger.info(f"Exported Markdown report to {md_path}")

            return str(path.parent)

        else:
            raise ValueError(
                f"Unknown format: {format}. Use 'json', 'markdown', or 'both'"
            )

        return str(path)

    def generate_summary_string(self, report: CacheEffectivenessReport) -> str:
        """
        Generate a concise summary string for console output.

        Args:
            report: The report to summarize

        Returns:
            Multi-line summary string
        """
        lines = [
            "",
            "╔════════════════════════════════════════════════════════╗",
            "║          Cache Effectiveness Summary                   ║",
            "╠════════════════════════════════════════════════════════╣",
            f"║  LLM Calls Saved:     {report.total_calls_saved:>12,}                      ║",
            f"║  Time Saved:          {report.total_time_saved_formatted:>20}              ║",
            f"║  Cost Saved:          {report.total_cost_saved_formatted:>12}                      ║",
            f"║  Cache Hit Rate:      {report.cache_hit_rate * 100:>11.1f}%                      ║",
            "╠════════════════════════════════════════════════════════╣",
            "║  Provider Breakdown                                    ║",
        ]

        for ps in report.provider_savings:
            lines.append(
                f"║    {ps.provider.capitalize():<10} {ps.calls_saved:>6,} calls  ${ps.cost_saved:>8.4f}  {ps.time_saved_formatted:>12}  ║"
            )

        lines.extend(
            [
                "╚════════════════════════════════════════════════════════╝",
                "",
            ]
        )

        return "\n".join(lines)


# Global reporter instance
_reporter_instance: Optional[CacheEffectivenessReporter] = None


def get_cache_reporter() -> CacheEffectivenessReporter:
    """
    Get or create the global cache reporter instance.

    Returns:
        The global CacheEffectivenessReporter instance
    """
    global _reporter_instance
    if _reporter_instance is None:
        _reporter_instance = CacheEffectivenessReporter()
    return _reporter_instance


def reset_cache_reporter() -> None:
    """Reset the global cache reporter instance."""
    global _reporter_instance
    _reporter_instance = None
