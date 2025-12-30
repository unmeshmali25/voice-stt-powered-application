#!/usr/bin/env python3
"""Test coupon availability for simulation agents."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv()

db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)
db = Session(engine)

# Get a simulation user
user_result = db.execute(
    text("""
    SELECT user_id FROM agents WHERE is_active = true LIMIT 1
""")
).fetchone()

if user_result and hasattr(user_result, "user_id"):
    user_id = str(user_result.user_id)
    print(f"Testing with user: {user_id[:8]}...")
    print()

    # Test 1: OLD WAY - using simulated time (should return 0)
    simulated_time = "2030-01-16"
    result_old = db.execute(
        text("""
        SELECT COUNT(*) as count
        FROM user_coupons uc
        JOIN coupons c ON uc.coupon_id = c.id
        WHERE uc.user_id = :user_id
          AND (uc.status = 'active' OR uc.status IS NULL)
          AND uc.eligible_until > :simulated_time
    """),
        {"user_id": user_id, "simulated_time": simulated_time},
    ).fetchone()

    print(f"Test 1 (OLD - using simulated time {simulated_time}):")
    print(f"  Coupons available: {result_old.count}")
    print()

    # Test 2: NEW WAY - using NOW() (should return coupons)
    result_new = db.execute(
        text("""
        SELECT COUNT(*) as count
        FROM user_coupons uc
        JOIN coupons c ON uc.coupon_id = c.id
        WHERE uc.user_id = :user_id
          AND (uc.status = 'active' OR uc.status IS NULL)
          AND uc.eligible_until > NOW()
    """),
        {"user_id": user_id},
    ).fetchone()

    print(f"Test 2 (NEW - using NOW()):")
    print(f"  Coupons available: {result_new.count}")
    print()

    # Show sample coupons
    result_sample = db.execute(
        text("""
        SELECT c.type, c.discount_details, uc.assigned_at, uc.eligible_until
        FROM user_coupons uc
        JOIN coupons c ON uc.coupon_id = c.id
        WHERE uc.user_id = :user_id
          AND uc.eligible_until > NOW()
        LIMIT 5
    """),
        {"user_id": user_id},
    ).fetchall()

    if result_sample:
        print("Sample available coupons:")
        for row in result_sample:
            print(f"  Type: {row.type}, Discount: {row.discount_details}")
            print(f"    Assigned: {row.assigned_at}, Expires: {row.eligible_until}")
    else:
        print("No coupons available (they may have all expired)")
else:
    print("No active agents found")

db.close()
