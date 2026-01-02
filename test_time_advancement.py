#!/usr/bin/env python3
"""Test time advancement to verify each cycle advances exactly 1 simulated hour."""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime, date, timedelta

load_dotenv()

# Set simulation mode
os.environ["SIMULATION_MODE"] = "true"

from app.offer_engine.config import OfferEngineConfig
from app.offer_engine.time_service import TimeService


def test_time_advancement():
    """Test that time_scale correctly advances simulated time."""
    print("=" * 70)
    print("Test: Time Scale Advancement Verification")
    print("=" * 70)
    print()

    # Test different time_scale values
    test_cases = [
        (24.0, "24x (1 real hour = 1 simulated day)"),
        (96.0, "96x (1 real hour = 4 simulated days)"),
        (168.0, "168x (1 real hour = 7 simulated days)"),
    ]

    for time_scale, description in test_cases:
        print(f"\nTesting {description}")
        print("-" * 70)

        # Initialize components
        config = OfferEngineConfig()
        config.simulation_mode = True
        config.time_scale = time_scale

        time_service = TimeService(config)
        time_service.start_simulation(calendar_start=date(2024, 1, 1))

        print(f"  time_scale: {config.time_scale}")
        print(f"  calendar_start: {time_service.get_simulated_date()}")
        print()

        # Test 1: Advance 1 real hour
        initial_sim_time = time_service.now()
        result1 = time_service.advance_time(hours=1.0)
        after1_sim_time = time_service.now()

        real_hours_advanced = result1.real_hours_advanced
        expected_sim_hours = real_hours_advanced * config.time_scale
        actual_sim_hours = (after1_sim_time - initial_sim_time).total_seconds() / 3600

        print(f"  Test 1: Advance 1 real hour")
        print(f"    Real hours advanced: {real_hours_advanced}")
        print(f"    Expected simulated hours: {expected_sim_hours:.2f}")
        print(f"    Actual simulated hours: {actual_sim_hours:.2f}")
        print(f"    Match: {abs(expected_sim_hours - actual_sim_hours) < 0.01}")

        if abs(expected_sim_hours - actual_sim_hours) >= 0.01:
            print(
                f"    ❌ FAILED: Expected {expected_sim_hours:.2f} hours, got {actual_sim_hours:.2f}"
            )
            return False
        else:
            print(f"    ✅ PASSED")
        print()

        # Test 2: Simulate 31 cycles (each cycle advances 1/time_scale real hours)
        time_service2 = TimeService(config)
        time_service2.start_simulation(calendar_start=date(2024, 1, 1))
        initial_date = time_service2.get_simulated_date()
        initial_datetime = time_service2.now()

        cycles = 31
        real_hours_per_cycle = 1.0 / config.time_scale
        total_real_hours = cycles * real_hours_per_cycle
        expected_sim_hours = total_real_hours * config.time_scale  # Should be 31 hours
        expected_sim_datetime = initial_datetime + timedelta(hours=expected_sim_hours)

        for i in range(cycles):
            time_service2.advance_time(hours=real_hours_per_cycle)

        final_datetime = time_service2.now()
        actual_sim_hours = (final_datetime - initial_datetime).total_seconds() / 3600

        print(f"  Test 2: Simulate {cycles} cycles")
        print(f"    Cycles: {cycles}")
        print(f"    Real hours per cycle: {real_hours_per_cycle:.4f}")
        print(f"    Total real hours: {total_real_hours:.4f}")
        print(f"    Expected simulated hours: {expected_sim_hours:.2f}")
        print(f"    Actual simulated hours: {actual_sim_hours:.2f}")
        print(f"    Initial datetime: {initial_datetime}")
        print(f"    Expected datetime: {expected_sim_datetime}")
        print(f"    Actual datetime: {final_datetime}")
        print(f"    Match: {abs(expected_sim_hours - actual_sim_hours) < 0.01}")

        if abs(expected_sim_hours - actual_sim_hours) >= 0.01:
            print(
                f"    ❌ FAILED: Expected {expected_sim_hours:.2f} hours, got {actual_sim_hours:.2f}"
            )
            return False
        else:
            print(f"    ✅ PASSED")
        print()

        # Test 3: Verify 24 cycles = 1 simulated day
        time_service3 = TimeService(config)
        time_service3.start_simulation(calendar_start=date(2021, 1, 1))
        initial_date3 = time_service3.get_simulated_date()

        for i in range(24):
            time_service3.advance_time(hours=1.0 / config.time_scale)

        final_date3 = time_service3.get_simulated_date()
        expected_date = date(2021, 1, 2)

        print(f"  Test 3: 24 cycles should equal 1 simulated day")
        print(f"    Initial date: {initial_date3}")
        print(f"    Expected date: {expected_date}")
        print(f"    Actual date: {final_date3}")
        print(f"    Match: {final_date3 == expected_date}")

        if final_date3 != expected_date:
            print(f"    ❌ FAILED: Expected {expected_date}, got {final_date3}")
            return False
        else:
            print(f"    ✅ PASSED")
        print()

    print("=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    return True


def test_dashboard_datetime_display():
    """Test that simulated datetime includes hours and minutes."""
    print("\n" + "=" * 70)
    print("Test: Dashboard Datetime Display")
    print("=" * 70)
    print()

    config = OfferEngineConfig()
    config.simulation_mode = True
    config.time_scale = 96.0

    time_service = TimeService(config)
    time_service.start_simulation(calendar_start=date(2024, 1, 1))

    initial_datetime = time_service.now()
    print(f"Initial simulated datetime: {initial_datetime}")
    print(f"  Includes time: {initial_datetime.hour}:{initial_datetime.minute:02d}")

    # Advance 12 simulated hours (12 cycles at 96x)
    for i in range(12):
        time_service.advance_time(hours=1.0 / 96.0)

    after_datetime = time_service.now()
    print(f"\nAfter 12 cycles (12 simulated hours): {after_datetime}")
    print(
        f"  Time difference: {(after_datetime - initial_datetime).total_seconds() / 3600:.2f} hours"
    )
    print(f"  Time shown: {after_datetime.hour}:{after_datetime.minute:02d}")

    time_diff = (after_datetime - initial_datetime).total_seconds() / 3600
    if abs(time_diff - 12.0) < 0.1:
        print("\n✅ PASSED: Time progression correct")
        return True
    else:
        print(f"\n❌ FAILED: Expected 12 hours, got {time_diff:.2f}")
        return False


if __name__ == "__main__":
    success = True

    success = test_time_advancement() and success
    success = test_dashboard_datetime_display() and success

    if not success:
        sys.exit(1)
    else:
        sys.exit(0)
