"""
Test script for the LLM metrics dashboard.

Usage:
    python tests/test_dashboard.py
"""

import asyncio
import sys

sys.path.insert(0, "/Users/unmeshmali/Downloads/Unmesh/VoiceOffers")

from app.simulation.metrics.llm_metrics import LLMMetricsCollector
from app.simulation.metrics.dashboard import MetricsDashboard, create_llm_dashboard


async def test_dashboard_basic():
    """Test that dashboard can be created and renders correctly."""
    print("Creating metrics collector...")
    collector = LLMMetricsCollector()

    # Simulate some activity
    print("Simulating LLM calls...")

    # Record some decisions
    await collector.record_llm_decision()
    await collector.record_llm_decision()
    await collector.record_probability_decision()

    # Record cache activity
    await collector.record_cache_hit()
    await collector.record_cache_hit()
    await collector.record_cache_miss()

    print("Creating dashboard...")
    dashboard = create_llm_dashboard(
        metrics_collector=collector,
        llm_percentage=0.4,
    )

    print("Building dashboard panel...")
    panel = dashboard.build_dashboard_panel()

    print("✓ Dashboard created successfully!")
    print(f"Panel title: {panel.title}")

    # Get current metrics
    metrics = dashboard.get_current_metrics()
    print("\nCurrent Metrics:")
    print(f"  - LLM Decisions: {metrics['decisions']['llm_decisions']}")
    print(f"  - Probability Decisions: {metrics['decisions']['probability_decisions']}")
    print(f"  - Cache Hit Rate: {metrics['cache']['hit_rate_percent']}")
    print(f"  - Uptime: {metrics['uptime_formatted']}")

    return True


async def test_dashboard_with_provider_metrics():
    """Test dashboard with provider-specific metrics."""
    print("\nTesting dashboard with provider metrics...")

    collector = LLMMetricsCollector()

    # Simulate Ollama calls
    await collector.start_call("ollama")
    await asyncio.sleep(0.1)
    await collector.end_call("ollama", latency=1.5, success=True)

    await collector.start_call("ollama")
    await asyncio.sleep(0.05)
    await collector.end_call("ollama", latency=0.8, success=True)

    # Simulate OpenRouter calls
    await collector.start_call("openrouter")
    await asyncio.sleep(0.08)
    await collector.end_call("openrouter", latency=0.6, success=True)

    # Record some decisions
    await collector.record_llm_decision()
    await collector.record_llm_decision()
    await collector.record_probability_decision()
    await collector.record_cache_hit()
    await collector.record_cache_miss()

    dashboard = create_llm_dashboard(
        metrics_collector=collector,
        llm_percentage=0.4,
    )

    # Build and verify panel renders
    panel = dashboard.build_dashboard_panel()

    metrics = dashboard.get_current_metrics()
    print("✓ Provider metrics captured:")
    print(f"  - Ollama calls: {metrics['providers']['ollama']['total_calls']}")
    print(f"  - OpenRouter calls: {metrics['providers']['openrouter']['total_calls']}")
    print(
        f"  - Ollama p50 latency: {metrics['providers']['ollama']['latency']['p50'] * 1000:.0f}ms"
    )
    print(
        f"  - OpenRouter p50 latency: {metrics['providers']['openrouter']['latency']['p50'] * 1000:.0f}ms"
    )

    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing LLM Metrics Dashboard")
    print("=" * 60)

    try:
        if await test_dashboard_basic():
            print("\n✅ Basic dashboard test passed!")

        if await test_dashboard_with_provider_metrics():
            print("\n✅ Provider metrics test passed!")

        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
