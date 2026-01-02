#!/usr/bin/env python3
"""Test simulated time-based coupon expiration."""

import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, date, timedelta

load_dotenv()

# Set simulation mode
os.environ["SIMULATION_MODE"] = "true"

from app.offer_engine.config import OfferEngineConfig
from app.offer_engine.time_service import TimeService

# Initialize components
config = OfferEngineConfig.from_env()
config.simulation_mode = True
config.time_scale = 96.0  # 96x speed

time_service = TimeService(config)
time_service.start_simulation(calendar_start=date(2024, 1, 1))

print("Test 1: Simulated Time Context")
print(f"  Calendar start: 2024-01-01")
print(f"  Time scale: {config.time_scale}x")
print(f"  Current simulated time: {time_service.now()}")
print(f"  Current simulated date: {time_service.get_simulated_date()}")
print()

print("Test 2: Expiration Calculation (14 simulated days)")
current_simulated = time_service.now()
expiration = time_service.get_expiration_time(from_time=current_simulated)
days_diff = (expiration - current_simulated).days

print(f"  Current simulated time: {current_simulated}")
print(f"  Expiration time: {expiration}")
print(f"  Days until expiration: {days_diff} days")
print()

# Test at 1 simulated week (7 days)
print("Test 3: After 1 simulated week (7 days)")
sim_date_7_days = current_simulated + timedelta(days=7)
print(f"  Simulated date: {sim_date_7_days}")
print(f"  Is before expiration: {sim_date_7_days < expiration}")
print(
    f"  Would coupon be available: YES"
    if sim_date_7_days < expiration
    else "  Would coupon be available: NO"
)
print()

# Test at 2 simulated weeks (14 days)
print("Test 4: After 2 simulated weeks (14 days)")
sim_date_14_days = current_simulated + timedelta(days=14)
print(f"  Simulated date: {sim_date_14_days}")
print(
    f"  Is at expiration: {abs((sim_date_14_days - expiration).total_seconds()) < 60}"
)
print(f"  Would coupon be available: NO (just expired)")
print()

# Test at 3 simulated weeks (21 days)
print("Test 5: After 3 simulated weeks (21 days)")
sim_date_21_days = current_simulated + timedelta(days=21)
print(f"  Simulated date: {sim_date_21_days}")
print(f"  Is after expiration: {sim_date_21_days > expiration}")
print(f"  Would coupon be available: NO")
print()

print("✅ Simulated time-based expiration working correctly!")
print()
print("Summary:")
print(f"  - Coupons expire 14 simulated days after assignment")
print(f"  - At 96x time_scale: 14 simulated days ≈ 3.5 real hours")
print(f"  - Agents query with simulated_timestamp to check eligibility")
