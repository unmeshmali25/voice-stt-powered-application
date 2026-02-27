"""Tests for the cache effectiveness reporter."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from app.simulation.metrics.cache_reporter import (
    CacheEffectivenessReporter,
    CacheEffectivenessReport,
    ProviderSavings,
    PRICING_PER_1K_TOKENS,
    DEFAULT_TOKENS_PER_REQUEST,
    get_cache_reporter,
    reset_cache_reporter,
)
from app.simulation.metrics.llm_metrics import LLMMetricsCollector


class TestProviderSavings:
    """Test ProviderSavings dataclass."""

    def test_time_saved_formatted_seconds(self):
        """Test time formatting for seconds."""
        savings = ProviderSavings(
            provider="ollama",
            calls_saved=10,
            time_saved_ms=45000,  # 45 seconds
        )
        assert savings.time_saved_formatted == "45.0s"

    def test_time_saved_formatted_minutes(self):
        """Test time formatting for minutes."""
        savings = ProviderSavings(
            provider="openrouter",
            calls_saved=10,
            time_saved_ms=300000,  # 5 minutes
        )
        assert savings.time_saved_formatted == "5.0 minutes"

    def test_time_saved_formatted_hours(self):
        """Test time formatting for hours."""
        savings = ProviderSavings(
            provider="openrouter",
            calls_saved=10,
            time_saved_ms=7200000,  # 2 hours
        )
        assert savings.time_saved_formatted == "2.00 hours"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        savings = ProviderSavings(
            provider="ollama",
            calls_saved=100,
            time_saved_ms=150000,
            input_tokens_saved=50000,
            output_tokens_saved=10000,
            cost_saved=0.0,
        )
        d = savings.to_dict()
        assert d["provider"] == "ollama"
        assert d["calls_saved"] == 100
        assert d["time_saved_seconds"] == 150.0
        assert d["cost_saved_formatted"] == "$0.0000"


class TestCacheEffectivenessReport:
    """Test CacheEffectivenessReport dataclass."""

    def test_total_time_saved_formatted_seconds(self):
        """Test total time formatting."""
        report = CacheEffectivenessReport(total_time_saved_ms=30000)
        assert "30 seconds" in report.total_time_saved_formatted

    def test_total_time_saved_formatted_minutes(self):
        """Test total time formatting for minutes."""
        report = CacheEffectivenessReport(total_time_saved_ms=120000)
        formatted = report.total_time_saved_formatted
        assert "2.0 minutes" in formatted
        assert "120000ms" in formatted

    def test_total_cost_saved_formatted(self):
        """Test cost formatting."""
        report = CacheEffectivenessReport(total_cost_saved=0.1234)
        assert report.total_cost_saved_formatted == "$0.1234"

    def test_to_dict_structure(self):
        """Test dictionary output structure."""
        report = CacheEffectivenessReport(
            simulation_id="test_001",
            total_cache_hits=100,
            total_cache_misses=50,
            cache_hit_rate=0.667,
            total_calls_saved=100,
            total_time_saved_ms=150000,
            total_cost_saved=0.5,
            provider_savings=[
                ProviderSavings(provider="ollama", calls_saved=60),
                ProviderSavings(provider="openrouter", calls_saved=40),
            ],
        )
        d = report.to_dict()
        assert "metadata" in d
        assert "cache_statistics" in d
        assert "savings_summary" in d
        assert "provider_breakdown" in d
        assert d["metadata"]["simulation_id"] == "test_001"
        assert d["cache_statistics"]["total_cache_hits"] == 100
        assert len(d["provider_breakdown"]) == 2

    def test_to_markdown_contains_key_sections(self):
        """Test markdown output contains expected sections."""
        report = CacheEffectivenessReport(
            simulation_id="test_001",
            total_cache_hits=100,
            total_cache_misses=50,
            cache_hit_rate=0.667,
            total_calls_saved=100,
            total_time_saved_ms=150000,
            total_cost_saved=0.5,
            provider_savings=[
                ProviderSavings(provider="ollama", calls_saved=60, cost_saved=0.0),
                ProviderSavings(provider="openrouter", calls_saved=40, cost_saved=0.5),
            ],
        )
        md = report.to_markdown()
        assert "# Cache Effectiveness Report" in md
        assert "Cache Performance" in md
        assert "Savings Summary" in md
        assert "Provider Breakdown" in md
        assert "100" in md  # Total calls saved
        assert "$0.5000" in md  # Cost saved


class TestCacheEffectivenessReporter:
    """Test CacheEffectivenessReporter class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        reporter = CacheEffectivenessReporter()
        assert reporter.pricing == PRICING_PER_1K_TOKENS
        assert reporter.default_tokens == DEFAULT_TOKENS_PER_REQUEST

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        custom_pricing = {"ollama": {"input": 0.0, "output": 0.0, "per_request": 0.0}}
        custom_tokens = {"input": 1000, "output": 200}
        reporter = CacheEffectivenessReporter(
            pricing_config=custom_pricing,
            default_tokens=custom_tokens,
        )
        assert reporter.pricing == custom_pricing
        assert reporter.default_tokens == custom_tokens

    def test_generate_report_basic(self):
        """Test basic report generation."""
        # Create mock metrics collector
        mock_collector = Mock(spec=LLMMetricsCollector)
        mock_collector.get_cache_summary.return_value = {
            "hits": 100,
            "misses": 50,
            "hit_rate": 0.667,
        }
        mock_collector.get_provider_summary.side_effect = lambda p: {
            "ollama": {
                "total_calls": 80,
                "latency": {"avg": 1.5, "count": 80},
            },
            "openrouter": {
                "total_calls": 20,
                "latency": {"avg": 2.0, "count": 20},
            },
        }.get(p, {})

        reporter = CacheEffectivenessReporter()
        report = reporter.generate_report(
            metrics_collector=mock_collector,
            simulation_id="test_sim",
        )

        assert report.simulation_id == "test_sim"
        assert report.total_cache_hits == 100
        assert report.total_cache_misses == 50
        assert report.cache_hit_rate == 0.667
        assert report.total_calls_saved == 100
        assert len(report.provider_savings) == 2
        assert report.report_duration_seconds >= 0

    def test_generate_report_no_cache_hits(self):
        """Test report generation with no cache hits."""
        mock_collector = Mock(spec=LLMMetricsCollector)
        mock_collector.get_cache_summary.return_value = {
            "hits": 0,
            "misses": 100,
            "hit_rate": 0.0,
        }
        mock_collector.get_provider_summary.return_value = {
            "total_calls": 50,
            "latency": {"avg": 1.0, "count": 50},
        }

        reporter = CacheEffectivenessReporter()
        report = reporter.generate_report(
            metrics_collector=mock_collector,
            simulation_id="test_sim",
        )

        assert report.total_cache_hits == 0
        assert report.total_calls_saved == 0
        assert report.total_time_saved_ms == 0.0
        assert report.total_cost_saved == 0.0

    def test_generate_report_no_calls_made(self):
        """Test report generation when no LLM calls were made."""
        mock_collector = Mock(spec=LLMMetricsCollector)
        mock_collector.get_cache_summary.return_value = {
            "hits": 50,
            "misses": 50,
            "hit_rate": 0.5,
        }
        mock_collector.get_provider_summary.return_value = {
            "total_calls": 0,
            "latency": {"avg": 0, "count": 0},
        }

        reporter = CacheEffectivenessReporter()
        report = reporter.generate_report(
            metrics_collector=mock_collector,
            simulation_id="test_sim",
        )

        # Should default to 50/50 split when no call data
        ollama_savings = next(
            s for s in report.provider_savings if s.provider == "ollama"
        )
        openrouter_savings = next(
            s for s in report.provider_savings if s.provider == "openrouter"
        )
        assert ollama_savings.calls_saved == 25  # 50 // 2
        assert openrouter_savings.calls_saved == 25  # 50 - 25

    def test_export_report_markdown(self):
        """Test exporting markdown report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = CacheEffectivenessReport(
                simulation_id="test_001",
                total_cache_hits=100,
            )
            reporter = CacheEffectivenessReporter()

            path = reporter.export_report(
                report,
                format="markdown",
                path=f"{tmpdir}/report.md",
            )

            assert Path(path).exists()
            content = Path(path).read_text()
            assert "# Cache Effectiveness Report" in content

    def test_export_report_json(self):
        """Test exporting JSON report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = CacheEffectivenessReport(
                simulation_id="test_001",
                total_cache_hits=100,
            )
            reporter = CacheEffectivenessReporter()

            path = reporter.export_report(
                report,
                format="json",
                path=f"{tmpdir}/report.json",
            )

            assert Path(path).exists()
            content = json.loads(Path(path).read_text())
            assert content["metadata"]["simulation_id"] == "test_001"

    def test_export_report_both(self):
        """Test exporting both formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = CacheEffectivenessReport(
                simulation_id="test_001",
                total_cache_hits=100,
            )
            reporter = CacheEffectivenessReporter()

            path = reporter.export_report(
                report,
                format="both",
                path=f"{tmpdir}/report",
            )

            # Should return directory path
            assert Path(path).exists()
            assert Path(f"{tmpdir}/report.json").exists()
            assert Path(f"{tmpdir}/report.md").exists()

    def test_export_report_auto_filename(self):
        """Test auto-generated filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = CacheEffectivenessReport(simulation_id="test_001")
            reporter = CacheEffectivenessReporter()

            path = reporter.export_report(
                report,
                format="markdown",
                output_dir=tmpdir,
            )

            assert "cache_report_test_001_" in path
            assert path.endswith(".md")

    def test_export_report_invalid_format(self):
        """Test exporting with invalid format raises error."""
        report = CacheEffectivenessReport()
        reporter = CacheEffectivenessReporter()

        with pytest.raises(ValueError, match="Unknown format"):
            reporter.export_report(report, format="xml")

    def test_generate_summary_string(self):
        """Test summary string generation."""
        report = CacheEffectivenessReport(
            simulation_id="test_001",
            total_calls_saved=68,
            total_time_saved_ms=102000,
            total_cost_saved=0.34,
            cache_hit_rate=0.68,
            provider_savings=[
                ProviderSavings(
                    provider="ollama",
                    calls_saved=40,
                    cost_saved=0.0,
                    time_saved_ms=60000,
                ),
                ProviderSavings(
                    provider="openrouter",
                    calls_saved=28,
                    cost_saved=0.34,
                    time_saved_ms=42000,
                ),
            ],
        )
        reporter = CacheEffectivenessReporter()
        summary = reporter.generate_summary_string(report)

        assert "Cache Effectiveness Summary" in summary
        assert "68" in summary  # Calls saved
        assert "0.3400" in summary or "$0.34" in summary  # Cost saved
        assert "68.0%" in summary  # Hit rate
        assert "Ollama" in summary
        assert "Openrouter" in summary

    def test_generate_summary_string_no_savings(self):
        """Test summary string with no savings."""
        report = CacheEffectivenessReport(
            total_calls_saved=0,
            provider_savings=[],
        )
        reporter = CacheEffectivenessReporter()
        summary = reporter.generate_summary_string(report)

        assert "Cache Effectiveness Summary" in summary
        assert "0" in summary


class TestGlobalFunctions:
    """Test global getter/reset functions."""

    def test_get_cache_reporter_singleton(self):
        """Test that get_cache_reporter returns singleton."""
        reset_cache_reporter()
        reporter1 = get_cache_reporter()
        reporter2 = get_cache_reporter()
        assert reporter1 is reporter2

    def test_reset_cache_reporter(self):
        """Test resetting the global reporter."""
        reporter1 = get_cache_reporter()
        reset_cache_reporter()
        reporter2 = get_cache_reporter()
        assert reporter1 is not reporter2


class TestCostCalculations:
    """Test cost calculation accuracy."""

    def test_openrouter_cost_calculation(self):
        """Test OpenRouter cost calculation."""
        mock_collector = Mock(spec=LLMMetricsCollector)
        mock_collector.get_cache_summary.return_value = {
            "hits": 100,
            "misses": 0,
            "hit_rate": 1.0,
        }
        mock_collector.get_provider_summary.side_effect = lambda p: {
            "ollama": {"total_calls": 0, "latency": {"avg": 0, "count": 0}},
            "openrouter": {"total_calls": 100, "latency": {"avg": 2.0, "count": 100}},
        }.get(p, {})

        reporter = CacheEffectivenessReporter()
        report = reporter.generate_report(mock_collector, "test")

        openrouter_savings = next(
            s for s in report.provider_savings if s.provider == "openrouter"
        )

        # Expected: 100 calls * (500 input + 100 output tokens)
        # Input cost: (500 * 100 / 1000) * $0.0015 = $0.075
        # Output cost: (100 * 100 / 1000) * $0.002 = $0.02
        # Request cost: 100 * $0.005 = $0.50
        # Total: ~$0.595
        expected_input_cost = (100 * 500 / 1000) * 0.0015
        expected_output_cost = (100 * 100 / 1000) * 0.002
        expected_request_cost = 100 * 0.005
        expected_total = (
            expected_input_cost + expected_output_cost + expected_request_cost
        )

        assert abs(openrouter_savings.cost_saved - expected_total) < 0.001

    def test_ollama_cost_is_zero(self):
        """Test that Ollama cost is always zero."""
        mock_collector = Mock(spec=LLMMetricsCollector)
        mock_collector.get_cache_summary.return_value = {
            "hits": 100,
            "misses": 0,
            "hit_rate": 1.0,
        }
        mock_collector.get_provider_summary.side_effect = lambda p: {
            "ollama": {"total_calls": 100, "latency": {"avg": 1.5, "count": 100}},
            "openrouter": {"total_calls": 0, "latency": {"avg": 0, "count": 0}},
        }.get(p, {})

        reporter = CacheEffectivenessReporter()
        report = reporter.generate_report(mock_collector, "test")

        ollama_savings = next(
            s for s in report.provider_savings if s.provider == "ollama"
        )
        assert ollama_savings.cost_saved == 0.0
