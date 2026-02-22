#!/usr/bin/env python3
"""Execute Sprint 3 migrations: Offer Visibility + Uplift Readiness."""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

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
    """Task 3.1: Track Offer Impressions - Add coupon_ids to view_coupons events"""
    print("\n=== Task 3.1: Track Offer Impressions ===")

    with engine.connect() as conn:
        # Check if coupon_ids already exists in any view_coupons events
        check_result = conn.execute(
            text("""
            SELECT COUNT(*) as count 
            FROM shopping_session_events 
            WHERE event_type = 'view_coupons' 
            AND payload ? 'coupon_ids'
            """)
        ).fetchone()

        if check_result and check_result[0] > 0:
            print(
                f"  Coupon_ids already present in {check_result[0]} view_coupons events. Skipping..."
            )
            conn.commit()
            return

        # Find all view_coupons events that need updating
        result = conn.execute(
            text("""
            SELECT sse.id, sse.user_id, sse.session_id, sse.created_at
            FROM shopping_session_events sse
            WHERE sse.event_type = 'view_coupons'
            AND sse.is_simulated = true
            ORDER BY sse.created_at
            """)
        )

        events_to_update = result.fetchall()
        print(
            f"  Found {len(events_to_update)} view_coupons events to update with coupon_ids"
        )

        updated_count = 0
        for event in events_to_update:
            event_id = event[0]
            user_id = event[1]
            event_time = event[3]

            # Find what coupons were available to this user at this time
            # Coupons assigned with eligible_until > event_time
            coupon_result = conn.execute(
                text("""
                SELECT DISTINCT c.id, c.type, c.category_or_brand
                FROM user_coupons uc
                JOIN coupons c ON uc.coupon_id = c.id
                WHERE uc.user_id = :user_id
                  AND uc.eligible_until > :event_time
                  AND (uc.status = 'active' OR uc.status IS NULL)
                """),
                {"user_id": user_id, "event_time": event_time},
            )

            coupons = coupon_result.fetchall()
            coupon_ids = [str(c[0]) for c in coupons]
            coupon_types = list(set([c[1] for c in coupons]))

            # Build enhanced payload with coupon_ids
            payload = {
                "coupon_count": len(coupon_ids),
                "coupon_types": coupon_types,
                "coupon_ids": coupon_ids,
            }

            # Update the event with coupon_ids
            conn.execute(
                text("""
                UPDATE shopping_session_events
                SET payload = :payload::jsonb
                WHERE id = :event_id
                """),
                {"event_id": event_id, "payload": str(payload).replace("'", '"')},
            )

            updated_count += 1
            if updated_count % 100 == 0:
                print(f"    Updated {updated_count} events...")

        conn.commit()
        print(f"  ✅ Updated {updated_count} view_coupons events with coupon_ids")


def run_migration_002():
    """Task 3.2: Add Coupon Rejection Reasons - Infer from session flow"""
    print("\n=== Task 3.2: Add Coupon Rejection Reasons ===")

    with engine.connect() as conn:
        # First, check if rejection_reason already exists
        check_result = conn.execute(
            text("""
            SELECT COUNT(*) as count 
            FROM shopping_session_events 
            WHERE event_type = 'coupon_apply' 
            AND payload ? 'rejection_reason'
            """)
        ).fetchone()

        # Find all completed checkout sessions that had view_coupons but no coupon_apply
        result = conn.execute(
            text("""
            WITH session_analysis AS (
                SELECT 
                    sse.session_id,
                    sse.user_id,
                    sse.created_at as view_time,
                    jsonb_array_length(sse.payload->'coupon_ids') as coupons_available,
                    EXISTS (
                        SELECT 1 FROM shopping_session_events sse2 
                        WHERE sse2.session_id = sse.session_id 
                        AND sse2.event_type = 'coupon_apply'
                    ) as had_coupon_apply,
                    (
                        SELECT COALESCE(SUM((sse3.payload->>'cart_value')::numeric), 0)
                        FROM shopping_session_events sse3 
                        WHERE sse3.session_id = sse.session_id 
                        AND sse3.event_type = 'cart_add_item'
                    ) as cart_subtotal
                FROM shopping_session_events sse
                WHERE sse.event_type = 'view_coupons'
                AND sse.is_simulated = true
                AND jsonb_array_length(sse.payload->'coupon_ids') > 0
            )
            SELECT * FROM session_analysis 
            WHERE NOT had_coupon_apply
            LIMIT 1000
            """)
        )

        sessions_without_coupons = result.fetchall()
        print(
            f"  Found {len(sessions_without_coupons)} sessions with viewed coupons but no application"
        )

        # Create rejection events for these sessions
        rejection_count = 0
        for session in sessions_without_coupons:
            session_id = session[0]
            user_id = session[1]
            view_time = session[2]
            coupons_available = session[3]
            cart_subtotal = session[5] or 0

            # Determine rejection reason
            if cart_subtotal == 0:
                reason = "cart_empty"
            elif cart_subtotal < 20:  # Assuming common min_purchase threshold
                reason = "min_purchase_not_met"
            else:
                reason = "not_relevant"  # Default for now

            # Insert rejection event
            conn.execute(
                text("""
                INSERT INTO shopping_session_events 
                (session_id, user_id, event_type, payload, created_at, is_simulated)
                VALUES (:session_id, :user_id, 'coupon_rejection', 
                        jsonb_build_object('rejection_reason', :reason, 'cart_subtotal', :cart_subtotal, 'coupons_available', :coupons_available), 
                        :created_at, true)
                """),
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "reason": reason,
                    "cart_subtotal": float(cart_subtotal),
                    "coupons_available": coupons_available,
                    "created_at": view_time,
                },
            )

            rejection_count += 1
            if rejection_count % 100 == 0:
                print(f"    Created {rejection_count} rejection events...")

        conn.commit()
        print(f"  ✅ Created {rejection_count} coupon_rejection events")


def run_migration_003():
    """Task 3.3: Build Uplift-Ready Views comparing holdout vs treatment"""
    print("\n=== Task 3.3: Build Uplift-Ready Views ===")

    with engine.connect() as conn:
        # Create view for offer cycle uplift analysis
        conn.execute(
            text("""
            DROP VIEW IF EXISTS v_offer_cycle_uplift CASCADE;
            
            CREATE VIEW v_offer_cycle_uplift AS
            WITH cycle_metrics AS (
                SELECT 
                    oc.id as offer_cycle_id,
                    oc.cycle_number,
                    oc.simulated_start_date,
                    oc.simulated_end_date,
                    uoc.user_id,
                    uoc.is_holdout,
                    -- Order metrics
                    COUNT(DISTINCT o.id) as order_count,
                    COALESCE(SUM(o.final_total), 0) as total_revenue,
                    COALESCE(AVG(o.final_total), 0) as avg_order_value,
                    COALESCE(SUM(o.discount_total), 0) as total_discounts,
                    -- Coupon metrics
                    COUNT(DISTINCT uc.coupon_id) as coupons_received,
                    COUNT(DISTINCT CASE WHEN uc.status = 'used' THEN uc.coupon_id END) as coupons_redeemed,
                    CASE WHEN COUNT(DISTINCT uc.coupon_id) > 0 
                         THEN COUNT(DISTINCT CASE WHEN uc.status = 'used' THEN uc.coupon_id END) * 100.0 / COUNT(DISTINCT uc.coupon_id)
                         ELSE 0 
                    END as redemption_rate
                FROM offer_cycles oc
                JOIN user_offer_cycles uoc ON uoc.current_cycle_id = oc.id
                LEFT JOIN user_coupons uc ON uc.offer_cycle_id = oc.id AND uc.user_id = uoc.user_id
                LEFT JOIN orders o ON o.user_id = uoc.user_id 
                    AND o.created_at BETWEEN oc.simulated_start_date AND oc.simulated_end_date
                    AND o.is_simulated = true
                WHERE oc.is_simulation = true
                GROUP BY oc.id, oc.cycle_number, oc.simulated_start_date, oc.simulated_end_date,
                         uoc.user_id, uoc.is_holdout
            )
            SELECT 
                offer_cycle_id,
                cycle_number,
                simulated_start_date,
                simulated_end_date,
                is_holdout,
                COUNT(DISTINCT user_id) as user_count,
                SUM(order_count) as total_orders,
                AVG(order_count) as avg_orders_per_user,
                SUM(total_revenue) as total_revenue,
                AVG(total_revenue) as avg_revenue_per_user,
                AVG(avg_order_value) as avg_order_value,
                SUM(total_discounts) as total_discounts,
                AVG(total_discounts) as avg_discounts_per_user,
                SUM(coupons_received) as total_coupons_sent,
                SUM(coupons_redeemed) as total_coupons_redeemed,
                AVG(redemption_rate) as avg_redemption_rate
            FROM cycle_metrics
            GROUP BY offer_cycle_id, cycle_number, simulated_start_date, simulated_end_date, is_holdout
            ORDER BY cycle_number, is_holdout;
            """)
        )
        print("  ✅ Created v_offer_cycle_uplift view")

        # Create summary view for overall uplift
        conn.execute(
            text("""
            DROP VIEW IF EXISTS v_uplift_summary CASCADE;
            
            CREATE VIEW v_uplift_summary AS
            WITH treatment_stats AS (
                SELECT 
                    AVG(avg_orders_per_user) as avg_orders_treatment,
                    AVG(avg_revenue_per_user) as avg_revenue_treatment,
                    AVG(avg_order_value) as avg_order_value_treatment,
                    AVG(avg_discounts_per_user) as avg_discounts_treatment,
                    AVG(avg_redemption_rate) as avg_redemption_rate_treatment
                FROM v_offer_cycle_uplift
                WHERE is_holdout = false
            ),
            holdout_stats AS (
                SELECT 
                    AVG(avg_orders_per_user) as avg_orders_holdout,
                    AVG(avg_revenue_per_user) as avg_revenue_holdout,
                    AVG(avg_order_value) as avg_order_value_holdout,
                    AVG(avg_discounts_per_user) as avg_discounts_holdout,
                    AVG(avg_redemption_rate) as avg_redemption_rate_holdout
                FROM v_offer_cycle_uplift
                WHERE is_holdout = true
            )
            SELECT 
                t.avg_orders_treatment,
                h.avg_orders_holdout,
                CASE WHEN h.avg_orders_holdout > 0 
                     THEN ((t.avg_orders_treatment - h.avg_orders_holdout) / h.avg_orders_holdout * 100)
                     ELSE 0 
                END as orders_uplift_pct,
                
                t.avg_revenue_treatment,
                h.avg_revenue_holdout,
                CASE WHEN h.avg_revenue_holdout > 0 
                     THEN ((t.avg_revenue_treatment - h.avg_revenue_holdout) / h.avg_revenue_holdout * 100)
                     ELSE 0 
                END as revenue_uplift_pct,
                
                t.avg_order_value_treatment,
                h.avg_order_value_holdout,
                CASE WHEN h.avg_order_value_holdout > 0 
                     THEN ((t.avg_order_value_treatment - h.avg_order_value_holdout) / h.avg_order_value_holdout * 100)
                     ELSE 0 
                END as aov_uplift_pct,
                
                t.avg_redemption_rate_treatment,
                h.avg_redemption_rate_holdout
            FROM treatment_stats t, holdout_stats h;
            """)
        )
        print("  ✅ Created v_uplift_summary view")

        # Create margin uplift view
        conn.execute(
            text("""
            DROP VIEW IF EXISTS v_margin_uplift CASCADE;
            
            CREATE VIEW v_margin_uplift AS
            WITH order_margins AS (
                SELECT 
                    o.id as order_id,
                    o.user_id,
                    o.final_total,
                    o.discount_total,
                    o.created_at,
                    uoc.is_holdout,
                    oc.cycle_number,
                    SUM(oi.quantity * COALESCE(p.cost, oi.product_price * 0.75)) as estimated_cost,
                    SUM(oi.quantity * oi.product_price) as gross_revenue
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.id
                LEFT JOIN products p ON p.id = oi.product_id
                LEFT JOIN user_offer_cycles uoc ON uoc.user_id = o.user_id
                LEFT JOIN offer_cycles oc ON oc.id = uoc.current_cycle_id
                    AND o.created_at BETWEEN oc.simulated_start_date AND oc.simulated_end_date
                WHERE o.is_simulated = true
                GROUP BY o.id, o.user_id, o.final_total, o.discount_total, o.created_at, uoc.is_holdout, oc.cycle_number
            ),
            margin_by_group AS (
                SELECT 
                    is_holdout,
                    COUNT(DISTINCT order_id) as order_count,
                    AVG(final_total - estimated_cost) as avg_margin_per_order,
                    SUM(final_total - estimated_cost) as total_margin,
                    AVG(final_total) as avg_order_value,
                    AVG(discount_total) as avg_discount
                FROM order_margins
                GROUP BY is_holdout
            )
            SELECT 
                t.order_count as treatment_orders,
                h.order_count as holdout_orders,
                t.avg_margin_per_order as treatment_avg_margin,
                h.avg_margin_per_order as holdout_avg_margin,
                CASE WHEN h.avg_margin_per_order != 0 
                     THEN ((t.avg_margin_per_order - h.avg_margin_per_order) / ABS(h.avg_margin_per_order) * 100)
                     ELSE 0 
                END as margin_uplift_pct,
                t.total_margin as treatment_total_margin,
                h.total_margin as holdout_total_margin,
                t.avg_discount as treatment_avg_discount,
                h.avg_discount as holdout_avg_discount
            FROM margin_by_group t
            CROSS JOIN margin_by_group h
            WHERE t.is_holdout = false AND h.is_holdout = true;
            """)
        )
        print("  ✅ Created v_margin_uplift view")

        conn.commit()
        print("\n  ✅ All uplift views created successfully")


if __name__ == "__main__":
    print("=" * 70)
    print("SPRINT 3: Offer Visibility + Uplift Readiness")
    print("=" * 70)

    try:
        run_migration_001()  # Task 3.1: Track Offer Impressions
        run_migration_002()  # Task 3.2: Add Coupon Rejection Reasons
        run_migration_003()  # Task 3.3: Build Uplift-Ready Views

        print("\n" + "=" * 70)
        print("✅ SPRINT 3 COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nSummary:")
        print("  • Task 3.1: Updated view_coupons events with coupon_ids")
        print("  • Task 3.2: Created coupon_rejection events with reasons")
        print("  • Task 3.3: Created 3 uplift analysis views")
        print("\nViews created:")
        print("  • v_offer_cycle_uplift - Per-cycle holdout vs treatment metrics")
        print("  • v_uplift_summary - Overall uplift percentages")
        print("  • v_margin_uplift - Margin comparison with discount impact")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
