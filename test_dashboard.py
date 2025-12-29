#!/usr/bin/env python3
"""
Quick test of debug mode dashboard with interrupt handling.
Run this and try pressing Ctrl+C to verify clean exit.
"""

import asyncio
import sys
from app.simulation.orchestrator import run_simulation


async def main():
    try:
        print("Starting test simulation...")
        print("Press Ctrl+C to stop cleanly")
        print("-" * 60)

        await run_simulation(
            duration_hours=0.02,  # Very short
            time_scale=96.0,
            debug_mode=True,
            show_dashboard=True,
            process_all_agents=False,
        )

        print("-" * 60)
        print("Simulation completed successfully!")
        return 0
    except KeyboardInterrupt:
        print("\n[yellow]Interrupted by user[/yellow]")
        return 130
    except Exception as e:
        print(f"\n[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
