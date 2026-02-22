#!/usr/bin/env python3
"""Execute Sprint 1 migrations for ML/RL readiness."""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL not found in environment")
    sys.exit(1)

# Fix postgres:// to postgresql:// for SQLAlchemy
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

print(f"Connecting to database...")
engine = create_engine(db_url)


def run_migration_001():
    """Task 1.1: Fix Coupon Linkage"""
    print("\n=== Task 1.1: Fix Coupon Linkage ===")

    with engine.connect() as conn:
        # Step 1: Add new columns
        print("Adding order_id and redeemed_at columns...")
        conn.execute(
            text("""
            ALTER TABLE user_coupons
                ADD COLUMN IF NOT EXISTS order_id UUID REFERENCES orders(id),
                ADD COLUMN IF NOT EXISTS redeemed_at TIMESTAMP WITH TIME ZONE
        """)
        )

        # Add indexes
        print("Creating indexes...")
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_user_coupons_order_id ON user_coupons(order_id)
        """)
        )
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_user_coupons_redeemed_at ON user_coupons(redeemed_at)
        """)
        )

        # Step 2: Update status to 'used' where coupons were applied in orders
        print("Backfilling used coupon status and linkage...")
        result = conn.execute(
            text("""
            WITH used_coupons AS (
                SELECT DISTINCT
                    o.id as order_id,
                    o.user_id,
                    oi.applied_coupon_id as coupon_id,
                    o.created_at as redeemed_at
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.id
                WHERE oi.applied_coupon_id IS NOT NULL
            )
            UPDATE user_coupons uc
            SET 
                status = 'used',
                order_id = uc_order.order_id,
                redeemed_at = uc_order.redeemed_at
            FROM used_coupons uc_order
            WHERE uc.user_id = uc_order.user_id
              AND uc.coupon_id = uc_order.coupon_id
              AND uc.status != 'used'
        """)
        )

        print(f"Updated {result.rowcount} coupons to 'used' status")

        # Validation
        used_count = conn.execute(
            text("""
            SELECT COUNT(*) FROM user_coupons WHERE status = 'used'
        """)
        ).scalar()

        linked_count = conn.execute(
            text("""
            SELECT COUNT(*) FROM user_coupons WHERE order_id IS NOT NULL
        """)
        ).scalar()

        orphaned_count = conn.execute(
            text("""
            SELECT COUNT(*) FROM user_coupons 
            WHERE status = 'used' AND order_id IS NULL
        """)
        ).scalar()

        print(f"\nValidation Results:")
        print(f"  - Coupons marked as 'used': {used_count}")
        print(f"  - Coupons linked to orders: {linked_count}")
        print(f"  - Orphaned 'used' coupons (should be 0): {orphaned_count}")

        conn.commit()

        if orphaned_count > 0:
            print("\nWARNING: Found orphaned used coupons!")
        else:
            print("\n✅ Task 1.1 completed successfully!")

        return used_count, linked_count


def run_migration_002():
    """Task 1.2: Add Product Margin Fields"""
    print("\n=== Task 1.2: Add Product Margin Fields ===")

    with engine.connect() as conn:
        # Step 1: Add columns
        print("Adding cost and margin_percent columns...")
        conn.execute(
            text("""
            ALTER TABLE products
                ADD COLUMN IF NOT EXISTS cost NUMERIC(10, 2),
                ADD COLUMN IF NOT EXISTS margin_percent NUMERIC(5, 2)
        """)
        )

        # Step 2: Populate margin_percent by category heuristics
        print("Populating margin_percent by category...")
        result = conn.execute(
            text("""
            UPDATE products
            SET margin_percent = CASE 
                WHEN category = 'Beauty' THEN 0.35
                WHEN category IN ('Personal Care', 'Skin Care', 'Hair Care', 'Oral Care') THEN 0.30
                WHEN category IN ('Paper Goods', 'Household') THEN 0.15
                WHEN category IN ('Over-the-Counter', 'Vitamins', 'First Aid') THEN 0.20
                WHEN category IN ('Baby Care', 'Pet Care') THEN 0.25
                WHEN category IN ('Snacks', 'Beverages') THEN 0.18
                WHEN category IN ('Office Supplies', 'Seasonal') THEN 0.28
                ELSE 0.20  -- Default 20% margin
            END
            WHERE margin_percent IS NULL
        """)
        )

        print(f"Updated {result.rowcount} products with margin percentages")

        # Step 3: Populate cost based on price and margin
        print("Calculating product costs...")
        result = conn.execute(
            text("""
            UPDATE products
            SET cost = price * (1 - margin_percent)
            WHERE cost IS NULL AND margin_percent IS NOT NULL
        """)
        )

        print(f"Updated {result.rowcount} products with cost values")

        # Validation
        null_margins = conn.execute(
            text("""
            SELECT COUNT(*) FROM products WHERE margin_percent IS NULL
        """)
        ).scalar()

        null_costs = conn.execute(
            text("""
            SELECT COUNT(*) FROM products WHERE cost IS NULL
        """)
        ).scalar()

        sample = conn.execute(
            text("""
            SELECT name, category, price, cost, margin_percent 
            FROM products 
            WHERE margin_percent IS NOT NULL
            LIMIT 5
        """)
        ).fetchall()

        print(f"\nValidation Results:")
        print(f"  - Products with NULL margin_percent: {null_margins}")
        print(f"  - Products with NULL cost: {null_costs}")
        print(f"\nSample products:")
        for p in sample:
            print(
                f"  - {p[0]}: ${p[2]:.2f} price, ${p[3]:.2f} cost, {p[4] * 100:.0f}% margin"
            )

        conn.commit()

        if null_margins == 0 and null_costs == 0:
            print("\n✅ Task 1.2 completed successfully!")
        else:
            print(
                f"\n⚠️  Task 1.2 completed with {null_margins} products missing margins"
            )

        return null_margins, null_costs


def run_migration_003():
    """Task 1.3: Add Holdout Groups"""
    print("\n=== Task 1.3: Add Holdout Groups ===")

    with engine.connect() as conn:
        # Step 1: Add columns
        print("Adding holdout fields...")
        conn.execute(
            text("""
            ALTER TABLE offer_cycles
                ADD COLUMN IF NOT EXISTS holdout_percentage NUMERIC(5, 2) DEFAULT 10.0
        """)
        )

        conn.execute(
            text("""
            ALTER TABLE user_offer_cycles
                ADD COLUMN IF NOT EXISTS is_holdout BOOLEAN DEFAULT FALSE
        """)
        )

        # Add index for queries
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_user_offer_cycles_is_holdout ON user_offer_cycles(is_holdout)
        """)
        )

        # Step 2: Update offer_cycles with default holdout
        print("Setting default holdout percentage on existing cycles...")
        result = conn.execute(
            text("""
            UPDATE offer_cycles
            SET holdout_percentage = 10.0
            WHERE holdout_percentage IS NULL
        """)
        )

        print(f"Updated {result.rowcount} offer cycles")

        # Step 3: Randomly assign 10% of users as holdout per cycle
        print("Assigning holdout users (10% per cycle)...")
        result = conn.execute(
            text("""
            WITH ranked_users AS (
                SELECT 
                    id,
                    current_cycle_id,
                    NTILE(10) OVER (PARTITION BY current_cycle_id ORDER BY RANDOM()) as decile
                FROM user_offer_cycles
                WHERE is_holdout = FALSE
            )
            UPDATE user_offer_cycles
            SET is_holdout = TRUE
            FROM ranked_users
            WHERE user_offer_cycles.id = ranked_users.id
              AND ranked_users.decile = 1
        """)
        )

        print(f"Assigned {result.rowcount} users to holdout groups")

        # Validation
        holdout_stats = conn.execute(
            text("""
            SELECT 
                current_cycle_id,
                COUNT(*) as total_users,
                SUM(CASE WHEN is_holdout THEN 1 ELSE 0 END) as holdout_users,
                ROUND(100.0 * SUM(CASE WHEN is_holdout THEN 1 ELSE 0 END) / COUNT(*), 1) as holdout_pct
            FROM user_offer_cycles
            GROUP BY current_cycle_id
            ORDER BY current_cycle_id
        """)
        ).fetchall()

        print(f"\nValidation Results:")
        print(f"{'Cycle':<8} {'Total':<8} {'Holdout':<8} {'%':<6}")
        print("-" * 35)
        for row in holdout_stats[:10]:  # Show first 10 cycles
            print(f"{str(row[0])[:8]:<8} {row[1]:<8} {row[2]:<8} {row[3]:<6}")

        if len(holdout_stats) > 10:
            print(f"... and {len(holdout_stats) - 10} more cycles")

        avg_holdout = conn.execute(
            text("""
            SELECT AVG(holdout_pct) FROM (
                SELECT 
                    current_cycle_id,
                    100.0 * SUM(CASE WHEN is_holdout THEN 1 ELSE 0 END) / COUNT(*) as holdout_pct
                FROM user_offer_cycles
                GROUP BY current_cycle_id
            ) subq
        """)
        ).scalar()

        conn.commit()

        print(f"\nAverage holdout rate: {avg_holdout:.1f}%")
        print("\n✅ Task 1.3 completed successfully!")

        return holdout_stats


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Sprint 1: ML/RL Readiness Database Migrations")
        print("=" * 60)

        # Run all migrations
        run_migration_001()
        run_migration_002()
        run_migration_003()

        print("\n" + "=" * 60)
        print("🎉 All Sprint 1 migrations completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error executing migrations: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
