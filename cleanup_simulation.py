#!/usr/bin/env python3
"""
Clean up all simulation data from database.
Run this before starting fresh simulations.

Usage:
    python cleanup_simulation.py          # With confirmation
    python cleanup_simulation.py --yes    # Automatic, no confirmation
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv()

# Check for --yes flag
auto_mode = "--yes" in sys.argv or "-y" in sys.argv

db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)
db = Session(engine)

print("=" * 70)
print("VoiceOffers Simulation Data Cleanup")
print("=" * 70)
print()

try:
    # Get counts before cleanup
    print("📊 Counting simulation data before cleanup...")
    print()

    # Order-related
    orders_before = db.execute(
        text("SELECT COUNT(*) FROM orders WHERE is_simulated = true")
    ).scalar()
    print(f"  Simulated orders: {orders_before}")

    # Shopping sessions
    sessions_before = db.execute(
        text("SELECT COUNT(*) FROM shopping_sessions WHERE is_simulated = true")
    ).scalar()
    print(f"  Simulated sessions: {sessions_before}")

    # User coupons
    coupons_before = db.execute(
        text("SELECT COUNT(*) FROM user_coupons WHERE is_simulation = true")
    ).scalar()
    print(f"  Simulation user coupons: {coupons_before}")

    # User offer cycles
    cycles_before = db.execute(
        text("SELECT COUNT(*) FROM user_offer_cycles WHERE is_simulation = true")
    ).scalar()
    print(f"  Simulation offer cycles: {cycles_before}")

    # Cart data
    cart_items = db.execute(
        text(
            """SELECT COUNT(*) FROM cart_items ci
           JOIN agents a ON ci.user_id = a.user_id
           WHERE a.is_active = true"""
        )
    ).scalar()
    print(f"  Cart items: {cart_items}")

    cart_coupons = db.execute(
        text(
            """SELECT COUNT(*) FROM cart_coupons cc
           JOIN agents a ON cc.user_id = a.user_id
           WHERE a.is_active = true"""
        )
    ).scalar()
    print(f"  Cart coupons: {cart_coupons}")
    print()

    # Confirm cleanup (unless auto mode)
    if not auto_mode:
        response = input(
            "⚠️  This will delete all simulation data. Continue? (yes/no): "
        )
        if response.lower() not in ["yes", "y"]:
            print("❌ Cleanup cancelled.")
            db.close()
            exit(0)

    print()
    print("🧹 Cleaning up simulation data...")
    print()

    # 1. Delete order_items for simulated orders
    result = db.execute(
        text(
            "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE is_simulated = true)"
        )
    )
    print(f"  ✅ Deleted simulated order items")

    # 2. Delete simulated orders
    result = db.execute(text("DELETE FROM orders WHERE is_simulated = true"))
    print(f"  ✅ Deleted simulated orders")

    # 3. Delete simulated shopping sessions
    result = db.execute(text("DELETE FROM shopping_sessions WHERE is_simulated = true"))
    print(f"  ✅ Deleted simulated shopping sessions")

    # 4. Delete cart items for agents
    result = db.execute(
        text(
            """DELETE FROM cart_items ci
           WHERE EXISTS (
               SELECT 1 FROM agents a
               WHERE a.user_id = ci.user_id AND a.is_active = true
           )"""
        )
    )
    print(f"  ✅ Deleted cart items")

    # 5. Delete cart coupons for agents
    result = db.execute(
        text(
            """DELETE FROM cart_coupons cc
           WHERE EXISTS (
               SELECT 1 FROM agents a
               WHERE a.user_id = cc.user_id AND a.is_active = true
           )"""
        )
    )
    print(f"  ✅ Deleted cart coupons")

    # 6. Delete coupon_interactions for simulated orders
    result = db.execute(
        text(
            """DELETE FROM coupon_interactions
           WHERE order_id IN (SELECT id FROM orders WHERE is_simulated = true)"""
        )
    )
    print(f"  ✅ Deleted coupon interactions")

    # 7. Delete user offer cycles
    result = db.execute(
        text("DELETE FROM user_offer_cycles WHERE is_simulation = true")
    )
    print(f"  ✅ Deleted user offer cycles")

    # 8. Delete user coupons
    result = db.execute(text("DELETE FROM user_coupons WHERE is_simulation = true"))
    print(f"  ✅ Deleted simulation user coupons")

    # 9. Reset simulation state
    db.execute(
        text("""
        UPDATE simulation_state
        SET is_active = false,
            current_simulated_date = NULL,
            simulation_calendar_start = NULL,
            simulation_start_time = NULL,
            real_start_time = NULL,
            time_scale = 168.0,
            updated_at = NOW()
        WHERE id = 1
    """)
    )
    print(f"  ✅ Reset simulation state")

    db.commit()
    print()
    print("=" * 70)
    print("✅ Cleanup completed successfully!")
    print("=" * 70)
    print()
    print("You can now run a fresh simulation:")
    print(
        "  python -m app.simulation.orchestrator --hours 4 --time-scale 96 --process-all-agents --debug"
    )

except Exception as e:
    db.rollback()
    print(f"\n❌ Error during cleanup: {e}")
    import traceback

    traceback.print_exc()

finally:
    db.close()
