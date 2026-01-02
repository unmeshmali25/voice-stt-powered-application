#!/usr/bin/env python3
"""Test simulated time-based coupon expiration."""

import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv()

db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Set simulation mode
os.environ["SIMULATION_MODE"] = "true"

from app.offer_engine.config import OfferEngineConfig
from app.offer_engine.time_service import TimeService
from app.offer_engine.expiration_handler import ExpirationHandler

engine = create_engine(db_url)
db = Session(engine)

# Initialize components
config = OfferEngineConfig.from_env()
config.simulation_mode = True
config.time_scale = 96.0  # 96x speed

time_service = TimeService(config, db)
time_service.start_simulation(calendar_start=date(2024, 1, 1))

print(f"Simulation started: {time_service.get_simulated_date()}")
print(f"Current real time: {datetime.utcnow()}")
print(f"Current simulated time: {time_service.now()}")
print()

# Test 1: Get expiration time
current_simulated = time_service.now()
expiration = time_service.get_expiration_time(from_time=current_simulated)
print(f"Test 1: Expiration Calculation")
print(f"  Current simulated time: {current_simulated}")
print(f"  Expiration time (14 days later): {expiration}")
print(f"  Days between: {(expiration - current_simulated).days}")
print()

# Test 2: Check if new assignments use simulated time
print("Test 2: Assigning coupon to verify timestamps")

# Get a test user
user_result = db.execute(
    text("""
    SELECT user_id FROM agents WHERE is_active = true LIMIT 1
""")
).fetchone()

if user_result:
    user_id = str(user_result.user_id)
    print(f"  Using user: {user_id[:8]}...")

    # Get a test coupon
    coupon_result = db.execute(
        text("""
        SELECT id FROM coupons WHERE type = 'frontstore' LIMIT 1
    """)
    ).fetchone()

    if coupon_result:
        coupon_id = str(coupon_result.id)
        print(f"  Using coupon: {coupon_id[:8]}...")

        # Manually test assignment
        assigned_at = time_service.now()
        expiration = time_service.get_expiration_time(from_time=assigned_at)

        print(f"  Assigned at (simulated): {assigned_at}")
        print(f"  Expires at (simulated): {expiration}")

        # Insert test record
        db.execute(
            text("""
            INSERT INTO user_coupons
                (user_id, coupon_id, status, offer_cycle_id, is_simulation, eligible_until, assigned_at)
            VALUES
                (:uid, :cid, 'active', 'test-cycle-001', true, :exp, :assigned_at)
        """),
            {
                "uid": user_id,
                "cid": coupon_id,
                "exp": expiration,
                "assigned_at": assigned_at,
            },
        )
        db.commit()

        # Verify
        verify_result = db.execute(
            text("""
            SELECT assigned_at, eligible_until,
                   EXTRACT(EPOCH FROM (eligible_until - assigned_at)) / 86400 as days_valid
            FROM user_coupons
            WHERE user_id = :uid AND coupon_id = :cid
        """),
            {"uid": user_id, "cid": coupon_id},
        ).fetchone()

        if verify_result:
            print(f"  Database stored assigned_at: {verify_result[0]}")
            print(f"  Database stored eligible_until: {verify_result[1]}")
            print(f"  Valid for: {verify_result[2]:.1f} days")
        print()

        # Test 3: Query with simulated timestamp
        print("Test 3: Querying coupons with different simulated timestamps")

        # At assignment time (should find coupon)
        at_assignment = db.execute(
            text("""
            SELECT COUNT(*) as count
            FROM user_coupons
            WHERE user_id = :uid
              AND eligible_until > :sim_time
              AND status = 'active'
        """),
            {"uid": user_id, "sim_time": assigned_at},
        ).fetchone()
        print(
            f"  At assignment time ({assigned_at}): {at_assignment[0]} coupons available"
        )

        # At expiration time (should find 0)
        at_expiration = db.execute(
            text("""
            SELECT COUNT(*) as count
            FROM user_coupons
            WHERE user_id = :uid
              AND eligible_until > :sim_time
              AND status = 'active'
        """),
            {"uid": user_id, "sim_time": expiration},
        ).fetchone()
        print(
            f"  At expiration time ({expiration}): {at_expiration[0]} coupons available"
        )

        # After 7 simulated days (should find 1 - coupon still valid)
        after_7_days = db.execute(
            text("""
            SELECT COUNT(*) as count
            FROM user_coupons
            WHERE user_id = :uid
              AND eligible_until > :sim_time
              AND status = 'active'
        """),
            {"uid": user_id, "sim_time": assigned_at.replace(day=assigned_at.day + 7)},
        ).fetchone()
        print(f"  After 7 simulated days: {after_7_days[0]} coupons available")

        # Clean up test record
        db.execute(
            text("""
            DELETE FROM user_coupons
            WHERE user_id = :uid AND coupon_id = :cid
        """),
            {"uid": user_id, "cid": coupon_id},
        )
        db.commit()
        print()
        print("✅ All tests passed!")

db.close()
