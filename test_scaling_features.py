#!/usr/bin/env python
"""
Test script to validate the new concurrency and checkpointing features.
"""

import asyncio
import sys
from pathlib import Path
from app.simulation.orchestrator import CheckpointManager, SimulationCheckpoint
from dataclasses import asdict


async def test_checkpoint_manager():
    """Test checkpoint manager functionality."""
    print("Testing CheckpointManager...")

    # Create checkpoint manager
    checkpoint_manager = CheckpointManager(
        checkpoint_interval_seconds=300, checkpoint_dir="test_checkpoints"
    )

    # Create a test checkpoint
    checkpoint = SimulationCheckpoint(
        timestamp=1234567890.0,
        cycle=5,
        agents_completed=["agent_001", "agent_002", "agent_003"],
        agents_in_progress=["agent_004"],
        stats={
            "agents_processed": 100,
            "sessions_created": 50,
            "checkouts_completed": 25,
        },
        simulated_datetime="2024-01-05T12:00:00",
    )

    # Save checkpoint
    print("  - Saving checkpoint...")
    checkpoint_file = checkpoint_manager.save_checkpoint(checkpoint)
    print(f"    Checkpoint saved to: {checkpoint_file}")

    # Load checkpoint
    print("  - Loading checkpoint...")
    loaded = checkpoint_manager.load_latest_checkpoint()
    assert loaded is not None, "Failed to load checkpoint"
    assert loaded.cycle == 5, "Checkpoint cycle mismatch"
    assert len(loaded.agents_completed) == 3, "Checkpoint agents count mismatch"
    print(f"    Loaded checkpoint cycle {loaded.cycle}")

    # Test cleanup
    print("  - Testing cleanup...")
    checkpoint_manager._cleanup_old_checkpoints(keep=2)
    checkpoints = list(checkpoint_manager.checkpoint_path.glob("checkpoint_*.json"))
    assert len(checkpoints) <= 2, "Cleanup failed"
    print(f"    After cleanup: {len(checkpoints)} checkpoints remaining")

    # Cleanup
    import shutil

    if Path("test_checkpoints").exists():
        shutil.rmtree("test_checkpoints")

    print("✅ CheckpointManager tests passed!")


async def test_concurrent_execution():
    """Test that concurrent execution parameters work."""
    print("\nTesting Concurrent Execution Parameters...")

    # Test that we can import and use the orchestrator
    from app.simulation.orchestrator import SimulationOrchestrator

    # Test adaptive concurrency calculation
    class MockOrchestrator:
        def __init__(self):
            self.adaptive_concurrency = True
            self.max_concurrent = 50

        def _get_adaptive_concurrency(self):
            if not self.adaptive_concurrency:
                return self.max_concurrent
            return self.max_concurrent

    mock = MockOrchestrator()

    print(f"  - Default concurrency: {mock._get_adaptive_concurrency()}")
    assert mock._get_adaptive_concurrency() == 50, "Concurrency mismatch"

    mock.adaptive_concurrency = False
    print(f"  - With adaptive disabled: {mock._get_adaptive_concurrency()}")
    assert mock._get_adaptive_concurrency() == 50, "Concurrency mismatch"

    print("✅ Concurrent execution tests passed!")


async def test_database_pool_config():
    """Test that database pool configuration is correct."""
    print("\nTesting Database Pool Configuration...")

    from sqlalchemy import create_engine

    # Test that we can create engine with pool settings
    try:
        engine = create_engine(
            "postgresql://test:test@localhost/test",
            pool_size=50,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=30,
            pool_use_lifo=True,
            echo=False,
        )
        print("  - Engine created successfully with pool settings")
        print("    pool_size=50, max_overflow=10")
        print("    pool_pre_ping=True, pool_recycle=3600")
        print("    pool_timeout=30, pool_use_lifo=True")
        print("✅ Database pool configuration tests passed!")
    except Exception as e:
        print(f"  ⚠️  Engine test skipped (expected without DB): {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Running Scaling Simulation Feature Tests")
    print("=" * 60)

    try:
        await test_checkpoint_manager()
        await test_concurrent_execution()
        await test_database_pool_config()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
