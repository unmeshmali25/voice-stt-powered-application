#!/usr/bin/env python3
"""
Calculate and explain time-scale relationships for VoiceOffers simulation.
"""

import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

# Get time_scale from env or use default
time_scale = float(os.getenv("TIME_SCALE", "96.0"))

print("=" * 70)
print(f"VoiceOffers Time-Scale Analysis (time_scale = {time_scale}x)")
print("=" * 70)
print()

print("📊 BASIC RELATIONSHIPS")
print("-" * 70)
print(f"Time Scale Definition: 1 real second = {time_scale} simulated seconds")
print()

# Real time → Simulated time
print("Real Time → Simulated Time:")
real_seconds = {
    "1 second": 1,
    "1 minute": 60,
    "1 hour": 3600,
    "1 day": 86400,
}

for name, seconds in real_seconds.items():
    sim_seconds = seconds * time_scale
    sim_days = sim_seconds / 86400
    print(
        f"  {name:10} = {sim_seconds:>10,.0f} simulated seconds = {sim_days:>6.2f} simulated days"
    )

print()

# Simulated time → Real time
print("Simulated Time → Real Time:")
sim_units = {
    "1 simulated second": 1,
    "1 simulated minute": 60,
    "1 simulated hour": 3600,
    "1 simulated day": 86400,
    "1 simulated week": 604800,
}

for name, sim_seconds in sim_units.items():
    real_seconds = sim_seconds / time_scale
    real_minutes = real_seconds / 60
    print(
        f"  {name:20} = {real_seconds:>10.2f} real seconds = {real_minutes:>6.2f} real minutes"
    )

print()

print("=" * 70)
print("🔄 SIMULATION CYCLE RELATIONSHIPS")
print("=" * 70)
print()

# Cycle calculation
# Scheduler advances 1 simulated hour per cycle
cycle_simulated_hours = 1

# Real time per cycle
real_seconds_per_cycle = 3600 / time_scale  # 1 hour / time_scale
real_minutes_per_cycle = real_seconds_per_cycle / 60

print(f"One Cycle:")
print(f"  Simulated time advanced: 1 hour")
print(
    f"  Real time elapsed: {real_seconds_per_cycle:.2f} seconds ({real_minutes_per_cycle:.2f} minutes)"
)
print()

# Cycles to reach milestones
milestones = [
    ("1 simulated day", 24, "days"),
    ("1 simulated week", 7 * 24, "days"),
    ("2 simulated weeks", 2 * 7 * 24, "days"),  # Coupon expiration
    ("1 simulated month", 30 * 24, "days"),
]

print("Cycles to Reach Milestones:")
for name, sim_hours, unit in milestones:
    cycles = sim_hours / cycle_simulated_hours
    real_time = cycles * real_seconds_per_cycle
    real_minutes = real_time / 60
    real_hours = real_time / 3600

    if unit == "days":
        print(
            f"  {name:20} = {cycles:>6,.1f} cycles = {real_minutes:>6.2f} min real time ({real_hours:.2f} hours)"
        )

print()

print("=" * 70)
print("💰 COUPON EXPIRATION TIMING")
print("=" * 70)
print()

# Coupon expiration is 14 simulated days
coupon_expiration_sim_days = 14
cycles_to_expire = (coupon_expiration_sim_days * 24) / cycle_simulated_hours
real_time_to_expire = cycles_to_expire * real_seconds_per_cycle

print(f"Coupon Validity: {coupon_expiration_sim_days} simulated days")
print(f"  Required cycles: {cycles_to_expire:,.1f}")
print(
    f"  Real time to expire: {real_time_to_expire / 60:.2f} minutes ({real_time_to_expire / 3600:.4f} hours)"
)
print()

# At different time scales
print("Expiration Time at Different Scales:")
scales = [24, 96, 168]
for scale in scales:
    seconds_per_cycle = 3600 / scale
    time_to_expire_hours = (coupon_expiration_sim_days * 24) * seconds_per_cycle / 3600
    time_to_expire_minutes = time_to_expire_hours * 60
    print(
        f"  {scale:3}x scale: {time_to_expire_minutes:>6.2f} minutes real time ({time_to_expire_hours:.2f} hours)"
    )

print()

print("=" * 70)
print("📅 OFFER CYCLE TIMING")
print("=" * 70)
print()

# Offer cycle is 7 simulated days (config.cycle_duration_days = 7)
offer_cycle_sim_days = 7
cycles_per_offer_cycle = (offer_cycle_sim_days * 24) / cycle_simulated_hours
real_time_per_offer_cycle = cycles_per_offer_cycle * real_seconds_per_cycle

print(f"Offer Cycle Duration: {offer_cycle_sim_days} simulated days")
print(f"  Required cycles: {cycles_per_offer_cycle:,.1f}")
print(
    f"  Real time per offer cycle: {real_time_per_offer_cycle / 60:.2f} minutes ({real_time_per_offer_cycle / 3600:.4f} hours)"
)
print()

print("Offer Cycle Time at Different Scales:")
for scale in scales:
    seconds_per_cycle = 3600 / scale
    cycles = (offer_cycle_sim_days * 24) / 1  # 1 simulated hour per cycle
    real_time = cycles * seconds_per_cycle
    print(
        f"  {scale:3}x scale: {real_time / 60:>6.2f} minutes real time ({real_time / 3600:.2f} hours)"
    )

print()

print("=" * 70)
print("🎯 PRACTICAL EXAMPLES")
print("=" * 70)
print()

print(f"Example 1: Running 4 real hours at {time_scale}x scale")
real_hours = 4
simulated_hours = real_hours * time_scale
simulated_days = simulated_hours / 24
print(f"  Real time: 4 hours")
print(f"  Simulated time: {simulated_hours:,.0f} hours = {simulated_days:.1f} days")
print(f"  Cycles completed: {simulated_hours:,.0f}")
print(f"  Offer cycles completed: {simulated_days / offer_cycle_sim_days:.1f}")
print()

print(f"Example 2: How long to simulate 1 year at {time_scale}x")
simulated_days_year = 365
simulated_hours_year = simulated_days_year * 24
real_hours_year = simulated_hours_year / time_scale
real_days_year = real_hours_year / 24
print(f"  Simulated time: 365 days (1 year)")
print(f"  Real time needed: {real_hours_year:.1f} hours = {real_days_year:.1f} days")
print()

print(f"Example 3: Coupon lifecycle at {time_scale}x")
print(f"  T+0h   (0 cycles):   Coupon assigned to user")
print(
    f"  T+{real_time_to_expire / 60:.1f}m ({cycles_to_expire:.0f} cycles): Coupon expires (14 sim days)"
)
print(f"  During valid period: User sees and can apply coupon")
print(f"  After expiration: User no longer sees coupon")
print()

print("=" * 70)
print("✅ Summary")
print("=" * 70)
print()
print(f"At time_scale = {time_scale}x:")
print(f"  • 1 cycle (1 sim hour) = {real_seconds_per_cycle:.2f} real seconds")
print(f"  • 1 simulated day = {24 * 3600 / time_scale / 60:.2f} real minutes")
print(
    f"  • Coupons expire after 14 simulated days = {real_time_to_expire / 60:.2f} real minutes"
)
print(
    f"  • Offer refreshes every 7 simulated days = {real_time_per_offer_cycle / 60:.2f} real minutes"
)
print()
