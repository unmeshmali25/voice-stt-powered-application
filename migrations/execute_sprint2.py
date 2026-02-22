#!/usr/bin/env python3
"""Execute Sprint 2 migrations: Daily State Snapshots + Rewards."""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
    """Task 2.1: Create Daily Agent State Snapshot Schema"""
    print("\n=== Task 2.1: Create Agent State Snapshot Schema ===")

    with engine.connect() as conn:
        # Step 1: Create the agent_state_snapshots table
        print("Creating agent_state_snapshots table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS agent_state_snapshots (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                snapshot_date DATE NOT NULL,
                
                -- Financial State
                remaining_budget DECIMAL(10, 2) NOT NULL DEFAULT 0,
                weekly_budget DECIMAL(10, 2) NOT NULL DEFAULT 0,
                spend_this_week DECIMAL(10, 2) NOT NULL DEFAULT 0,
                spend_this_month DECIMAL(10, 2) NOT NULL DEFAULT 0,
                
                -- Purchase History State
                days_since_last_purchase INTEGER,
                total_orders_lifetime INTEGER NOT NULL DEFAULT 0,
                total_orders_this_week INTEGER NOT NULL DEFAULT 0,
                
                -- Cart State
                cart_value DECIMAL(10, 2) NOT NULL DEFAULT 0,
                cart_item_count INTEGER NOT NULL DEFAULT 0,
                has_active_cart BOOLEAN NOT NULL DEFAULT FALSE,
                
                -- Browse Behavior
                products_viewed_count INTEGER NOT NULL DEFAULT 0,
                sessions_count_today INTEGER NOT NULL DEFAULT 0,
                sessions_count_this_week INTEGER NOT NULL DEFAULT 0,
                
                -- Category Diversity
                categories_purchased_count INTEGER NOT NULL DEFAULT 0,
                categories_purchased_this_week INTEGER NOT NULL DEFAULT 0,
                diversity_ratio DECIMAL(5, 4),  -- unique categories / total categories
                
                -- Time/Day Preference Match Flags
                pref_day_match BOOLEAN DEFAULT FALSE,
                pref_time_match BOOLEAN DEFAULT FALSE,
                
                -- Coupon State
                active_coupons_count INTEGER NOT NULL DEFAULT 0,
                coupons_redeemed_this_week INTEGER NOT NULL DEFAULT 0,
                
                -- Agent Traits (denormalized for RL state)
                price_sensitivity DECIMAL(3, 2),
                brand_loyalty DECIMAL(3, 2),
                impulsivity DECIMAL(3, 2),
                tech_savviness DECIMAL(3, 2),
                coupon_affinity DECIMAL(3, 2),
                
                -- Temporal Preferences (denormalized)
                pref_day_weekday DECIMAL(3, 2),
                pref_day_saturday DECIMAL(3, 2),
                pref_day_sunday DECIMAL(3, 2),
                pref_time_morning DECIMAL(3, 2),
                pref_time_afternoon DECIMAL(3, 2),
                pref_time_evening DECIMAL(3, 2),
                
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(agent_id, snapshot_date)
            )
            """)
        )

        # Step 2: Create indexes for efficient querying
        print("Creating indexes...")
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_state_agent_id ON agent_state_snapshots(agent_id)
            """)
        )
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_state_date ON agent_state_snapshots(snapshot_date)
            """)
        )
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_state_agent_date ON agent_state_snapshots(agent_id, snapshot_date)
            """)
        )

        # Step 3: Create trigger for updated_at
        conn.execute(
            text("""
            DROP TRIGGER IF EXISTS trigger_agent_state_updated_at ON agent_state_snapshots;
            """)
        )
        conn.execute(
            text("""
            CREATE TRIGGER trigger_agent_state_updated_at
                BEFORE UPDATE ON agent_state_snapshots
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """)
        )

        conn.commit()

        # Validation
        table_exists = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'agent_state_snapshots'
            )
            """)
        ).scalar()

        column_count = conn.execute(
            text("""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name = 'agent_state_snapshots'
            """)
        ).scalar()

        print(f"\nValidation Results:")
        print(f"  - Table exists: {table_exists}")
        print(f"  - Column count: {column_count}")

        if table_exists:
            print("\n✅ Task 2.1 completed successfully!")
        else:
            print("\n❌ Task 2.1 failed - table not created")

        return table_exists, column_count


def run_migration_002():
    """Task 2.2: Build Post-hoc Daily Snapshot ETL"""
    print("\n=== Task 2.2: Build Post-hoc Daily Snapshot ETL ===")

    with engine.connect() as conn:
        # Step 1: Get date range from existing orders
        print("Determining date range from orders...")
        date_range = conn.execute(
            text("""
            SELECT 
                MIN(DATE(created_at)) as min_date,
                MAX(DATE(created_at)) as max_date,
                COUNT(DISTINCT DATE(created_at)) as total_days
            FROM orders
            WHERE is_simulated = true
            """)
        ).fetchone()

        if not date_range or not date_range[0]:
            print("No simulated orders found. Skipping ETL.")
            return 0

        min_date, max_date, total_days = date_range
        print(f"Date range: {min_date} to {max_date} ({total_days} days)")

        # Step 2: Create a function to compute daily snapshots
        print("Creating snapshot computation query...")

        # Get all agents
        agents_result = conn.execute(
            text("SELECT id FROM agents WHERE is_active = true")
        ).fetchall()
        agents = [row[0] for row in agents_result]
        print(f"Found {len(agents)} active agents")

        if len(agents) == 0:
            print("No active agents found. Skipping ETL.")
            return 0

        # Step 3: Generate daily snapshots for each agent
        total_snapshots = 0
        current_date = min_date

        print("\nGenerating daily snapshots...")

        while current_date <= max_date:
            # For each date, compute state for all agents
            result = conn.execute(
                text("""
                INSERT INTO agent_state_snapshots (
                    agent_id, snapshot_date,
                    remaining_budget, weekly_budget, spend_this_week, spend_this_month,
                    days_since_last_purchase, total_orders_lifetime, total_orders_this_week,
                    cart_value, cart_item_count, has_active_cart,
                    products_viewed_count, sessions_count_today, sessions_count_this_week,
                    categories_purchased_count, categories_purchased_this_week, diversity_ratio,
                    pref_day_match, pref_time_match,
                    active_coupons_count, coupons_redeemed_this_week,
                    price_sensitivity, brand_loyalty, impulsivity, tech_savviness, coupon_affinity,
                    pref_day_weekday, pref_day_saturday, pref_day_sunday,
                    pref_time_morning, pref_time_afternoon, pref_time_evening
                )
                SELECT 
                    a.id as agent_id,
                    :snapshot_date as snapshot_date,
                    
                    -- Financial State
                    COALESCE(a.weekly_budget, 100) - COALESCE(weekly_spend.spend, 0) as remaining_budget,
                    COALESCE(a.weekly_budget, 100) as weekly_budget,
                    COALESCE(weekly_spend.spend, 0) as spend_this_week,
                    COALESCE(monthly_spend.spend, 0) as spend_this_month,
                    
                    -- Purchase History
                    (:snapshot_date - COALESCE(last_order.last_order_date, :snapshot_date)) as days_since_last_purchase,
                    COALESCE(lifetime_orders.count, 0) as total_orders_lifetime,
                    COALESCE(weekly_orders.count, 0) as total_orders_this_week,
                    
                    -- Cart State (active cart at snapshot time)
                    COALESCE(cart.value, 0) as cart_value,
                    COALESCE(cart.item_count, 0) as cart_item_count,
                    COALESCE(cart.has_items, false) as has_active_cart,
                    
                    -- Browse Behavior
                    COALESCE(products_viewed.count, 0) as products_viewed_count,
                    COALESCE(today_sessions.count, 0) as sessions_count_today,
                    COALESCE(week_sessions.count, 0) as sessions_count_this_week,
                    
                    -- Category Diversity
                    COALESCE(lifetime_categories.count, 0) as categories_purchased_count,
                    COALESCE(week_categories.count, 0) as categories_purchased_this_week,
                    CASE 
                        WHEN COALESCE(lifetime_categories.count, 0) > 0 
                        THEN COALESCE(lifetime_categories.count, 0)::DECIMAL / 20.0
                        ELSE 0 
                    END as diversity_ratio,
                    
                    -- Time/Day Preference Match
                    CASE 
                        WHEN EXTRACT(DOW FROM :snapshot_date) IN (1,2,3,4,5) AND COALESCE(a.pref_day_weekday, 0) > 0.5 THEN true
                        WHEN EXTRACT(DOW FROM :snapshot_date) = 6 AND COALESCE(a.pref_day_saturday, 0) > 0.5 THEN true
                        WHEN EXTRACT(DOW FROM :snapshot_date) = 0 AND COALESCE(a.pref_day_sunday, 0) > 0.5 THEN true
                        ELSE false
                    END as pref_day_match,
                    -- Time match depends on snapshot time - assume afternoon for ETL
                    CASE 
                        WHEN COALESCE(a.pref_time_afternoon, 0) > 0.5 THEN true
                        ELSE false
                    END as pref_time_match,
                    
                    -- Coupon State
                    COALESCE(active_coupons.count, 0) as active_coupons_count,
                    COALESCE(redeemed_coupons.count, 0) as coupons_redeemed_this_week,
                    
                    -- Agent Traits
                    a.price_sensitivity,
                    a.brand_loyalty,
                    a.impulsivity,
                    a.tech_savviness,
                    a.coupon_affinity,
                    
                    -- Temporal Preferences
                    a.pref_day_weekday,
                    a.pref_day_saturday,
                    a.pref_day_sunday,
                    a.pref_time_morning,
                    a.pref_time_afternoon,
                    a.pref_time_evening
                    
                FROM agents a
                
                -- Weekly spend
                LEFT JOIN (
                    SELECT o.user_id, SUM(o.final_total) as spend
                    FROM orders o
                    WHERE o.is_simulated = true
                      AND o.created_at >= :week_start
                      AND o.created_at < :week_end
                    GROUP BY o.user_id
                ) weekly_spend ON weekly_spend.user_id = a.user_id
                
                -- Monthly spend
                LEFT JOIN (
                    SELECT o.user_id, SUM(o.final_total) as spend
                    FROM orders o
                    WHERE o.is_simulated = true
                      AND o.created_at >= :month_start
                      AND o.created_at < :month_end
                    GROUP BY o.user_id
                ) monthly_spend ON monthly_spend.user_id = a.user_id
                
                -- Last order date
                LEFT JOIN (
                    SELECT o.user_id, MAX(DATE(o.created_at)) as last_order_date
                    FROM orders o
                    WHERE o.is_simulated = true
                      AND DATE(o.created_at) <= :snapshot_date
                    GROUP BY o.user_id
                ) last_order ON last_order.user_id = a.user_id
                
                -- Lifetime orders
                LEFT JOIN (
                    SELECT o.user_id, COUNT(*) as count
                    FROM orders o
                    WHERE o.is_simulated = true
                      AND DATE(o.created_at) <= :snapshot_date
                    GROUP BY o.user_id
                ) lifetime_orders ON lifetime_orders.user_id = a.user_id
                
                -- Weekly orders
                LEFT JOIN (
                    SELECT o.user_id, COUNT(*) as count
                    FROM orders o
                    WHERE o.is_simulated = true
                      AND o.created_at >= :week_start
                      AND o.created_at < :week_end
                    GROUP BY o.user_id
                ) weekly_orders ON weekly_orders.user_id = a.user_id
                
                -- Cart state (join via user_id)
                LEFT JOIN (
                    SELECT 
                        ci.user_id,
                        SUM(p.price * ci.quantity) as value,
                        SUM(ci.quantity) as item_count,
                        true as has_items
                    FROM cart_items ci
                    JOIN products p ON p.id = ci.product_id
                    WHERE ci.user_id IN (SELECT user_id FROM agents WHERE is_active = true)
                    GROUP BY ci.user_id
                ) cart ON cart.user_id = a.user_id
                
                -- Products viewed today
                LEFT JOIN (
                    SELECT sse.user_id, COUNT(*) as count
                    FROM shopping_session_events sse
                    WHERE sse.event_type = 'product_viewed'
                      AND DATE(sse.created_at) = :snapshot_date
                    GROUP BY sse.user_id
                ) products_viewed ON products_viewed.user_id = a.user_id
                
                -- Today's sessions
                LEFT JOIN (
                    SELECT ss.user_id, COUNT(*) as count
                    FROM shopping_sessions ss
                    WHERE DATE(ss.started_at) = :snapshot_date
                    GROUP BY ss.user_id
                ) today_sessions ON today_sessions.user_id = a.user_id
                
                -- This week's sessions
                LEFT JOIN (
                    SELECT ss.user_id, COUNT(*) as count
                    FROM shopping_sessions ss
                    WHERE ss.started_at >= :week_start
                      AND ss.started_at < :week_end
                    GROUP BY ss.user_id
                ) week_sessions ON week_sessions.user_id = a.user_id
                
                -- Lifetime categories
                LEFT JOIN (
                    SELECT o.user_id, COUNT(DISTINCT p.category) as count
                    FROM orders o
                    JOIN order_items oi ON oi.order_id = o.id
                    JOIN products p ON p.id = oi.product_id
                    WHERE o.is_simulated = true
                      AND DATE(o.created_at) <= :snapshot_date
                    GROUP BY o.user_id
                ) lifetime_categories ON lifetime_categories.user_id = a.user_id
                
                -- This week's categories
                LEFT JOIN (
                    SELECT o.user_id, COUNT(DISTINCT p.category) as count
                    FROM orders o
                    JOIN order_items oi ON oi.order_id = o.id
                    JOIN products p ON p.id = oi.product_id
                    WHERE o.is_simulated = true
                      AND o.created_at >= :week_start
                      AND o.created_at < :week_end
                    GROUP BY o.user_id
                ) week_categories ON week_categories.user_id = a.user_id
                
                -- Active coupons
                LEFT JOIN (
                    SELECT uc.user_id, COUNT(*) as count
                    FROM user_coupons uc
                    WHERE uc.status = 'active'
                    GROUP BY uc.user_id
                ) active_coupons ON active_coupons.user_id = a.user_id
                
                -- Redeemed coupons this week
                LEFT JOIN (
                    SELECT uc.user_id, COUNT(*) as count
                    FROM user_coupons uc
                    WHERE uc.status = 'used'
                      AND uc.redeemed_at >= :week_start
                      AND uc.redeemed_at < :week_end
                    GROUP BY uc.user_id
                ) redeemed_coupons ON redeemed_coupons.user_id = a.user_id
                
                WHERE a.is_active = true
                
                ON CONFLICT (agent_id, snapshot_date) 
                DO UPDATE SET
                    remaining_budget = EXCLUDED.remaining_budget,
                    spend_this_week = EXCLUDED.spend_this_week,
                    spend_this_month = EXCLUDED.spend_this_month,
                    days_since_last_purchase = EXCLUDED.days_since_last_purchase,
                    total_orders_lifetime = EXCLUDED.total_orders_lifetime,
                    total_orders_this_week = EXCLUDED.total_orders_this_week,
                    cart_value = EXCLUDED.cart_value,
                    cart_item_count = EXCLUDED.cart_item_count,
                    has_active_cart = EXCLUDED.has_active_cart,
                    products_viewed_count = EXCLUDED.products_viewed_count,
                    sessions_count_today = EXCLUDED.sessions_count_today,
                    sessions_count_this_week = EXCLUDED.sessions_count_this_week,
                    categories_purchased_count = EXCLUDED.categories_purchased_count,
                    categories_purchased_this_week = EXCLUDED.categories_purchased_this_week,
                    diversity_ratio = EXCLUDED.diversity_ratio,
                    pref_day_match = EXCLUDED.pref_day_match,
                    pref_time_match = EXCLUDED.pref_time_match,
                    active_coupons_count = EXCLUDED.active_coupons_count,
                    coupons_redeemed_this_week = EXCLUDED.coupons_redeemed_this_week,
                    updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "snapshot_date": current_date,
                    "week_start": current_date - timedelta(days=current_date.weekday()),
                    "week_end": current_date
                    - timedelta(days=current_date.weekday())
                    + timedelta(days=7),
                    "month_start": current_date.replace(day=1),
                    "month_end": (
                        current_date.replace(day=1) + timedelta(days=32)
                    ).replace(day=1),
                },
            )

            total_snapshots += result.rowcount

            if (current_date - min_date).days % 7 == 0:
                print(
                    f"  Processed {current_date} - {result.rowcount} snapshots created"
                )

            current_date += timedelta(days=1)

        conn.commit()

        # Validation: Spot check 3 agents
        print("\nValidation: Spot-checking 3 agents...")
        sample_agents = conn.execute(
            text("""
            SELECT agent_id, snapshot_date, remaining_budget, spend_this_week, 
                   days_since_last_purchase, cart_value, diversity_ratio
            FROM agent_state_snapshots
            ORDER BY RANDOM()
            LIMIT 3
            """)
        ).fetchall()

        print(f"\nSample snapshots:")
        for row in sample_agents:
            print(f"  Agent {str(row[0])[:8]}... on {row[1]}:")
            print(f"    Budget: ${row[2]:.2f} remaining, ${row[3]:.2f} spent this week")
            print(f"    Days since purchase: {row[4]}, Cart: ${row[5]:.2f}")
            print(f"    Diversity ratio: {row[6]:.3f}")

        # Get total stats
        total_count = conn.execute(
            text("SELECT COUNT(*) FROM agent_state_snapshots")
        ).scalar()

        date_coverage = conn.execute(
            text("SELECT COUNT(DISTINCT snapshot_date) FROM agent_state_snapshots")
        ).scalar()

        print(f"\nSummary:")
        print(f"  - Total snapshots created: {total_count}")
        print(f"  - Days covered: {date_coverage}")
        print(f"  - Average snapshots per day: {total_count // max(date_coverage, 1)}")

        print("\n✅ Task 2.2 completed successfully!")

        return total_count


def run_migration_003():
    """Task 2.3: Create Multi-Objective Reward Tables + Baseline Weights"""
    print("\n=== Task 2.3: Create Multi-Objective Reward Tables ===")

    with engine.connect() as conn:
        # Step 1: Create reward_weights table (configurable weights)
        print("Creating reward_weights configuration table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS reward_weights (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                
                -- Component weights (must sum to 1.0)
                profit_weight DECIMAL(4, 3) NOT NULL DEFAULT 0.40,
                satisfaction_weight DECIMAL(4, 3) NOT NULL DEFAULT 0.30,
                frequency_weight DECIMAL(4, 3) NOT NULL DEFAULT 0.20,
                diversity_weight DECIMAL(4, 3) NOT NULL DEFAULT 0.10,
                
                -- Component parameters
                profit_margin_threshold DECIMAL(5, 4) DEFAULT 0.15,  -- Minimum acceptable margin
                satisfaction_discount_threshold DECIMAL(5, 4) DEFAULT 0.20,  -- Target discount rate
                frequency_target_days INTEGER DEFAULT 7,  -- Target days between purchases
                diversity_target_ratio DECIMAL(5, 4) DEFAULT 0.30,  -- Target category diversity
                
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                CONSTRAINT weights_sum_to_one CHECK (
                    profit_weight + satisfaction_weight + frequency_weight + diversity_weight = 1.0
                )
            )
            """)
        )

        # Step 2: Insert default business-focused weights
        print("Inserting default business-focused weights...")
        conn.execute(
            text("""
            INSERT INTO reward_weights (name, profit_weight, satisfaction_weight, frequency_weight, diversity_weight)
            VALUES ('business_focused', 0.40, 0.30, 0.20, 0.10)
            ON CONFLICT (name) DO UPDATE SET
                profit_weight = EXCLUDED.profit_weight,
                satisfaction_weight = EXCLUDED.satisfaction_weight,
                frequency_weight = EXCLUDED.frequency_weight,
                diversity_weight = EXCLUDED.diversity_weight,
                updated_at = CURRENT_TIMESTAMP
            """)
        )

        # Step 3: Create agent_daily_rewards table
        print("Creating agent_daily_rewards table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS agent_daily_rewards (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                reward_date DATE NOT NULL,
                reward_weights_id INTEGER REFERENCES reward_weights(id),
                
                -- Reward Components (normalized to roughly -1 to +1 scale)
                profit_reward DECIMAL(10, 6),  -- Based on margin minus discount
                satisfaction_reward DECIMAL(10, 6),  -- Based on discount received
                frequency_reward DECIMAL(10, 6),  -- Based on purchase timing vs target
                diversity_reward DECIMAL(10, 6),  -- Based on category spread
                
                -- Raw metrics (for debugging/analysis)
                total_revenue DECIMAL(10, 2),
                total_cost DECIMAL(10, 2),
                total_profit DECIMAL(10, 2),
                avg_discount_rate DECIMAL(5, 4),
                days_since_last_purchase INTEGER,
                unique_categories_count INTEGER,
                
                -- Weighted total
                total_reward DECIMAL(10, 6),
                
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(agent_id, reward_date, reward_weights_id)
            )
            """)
        )

        # Step 4: Create indexes
        print("Creating indexes...")
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_rewards_agent_id ON agent_daily_rewards(agent_id)
            """)
        )
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_rewards_date ON agent_daily_rewards(reward_date)
            """)
        )
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_rewards_agent_date ON agent_daily_rewards(agent_id, reward_date)
            """)
        )
        conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_agent_rewards_total ON agent_daily_rewards(total_reward)
            """)
        )

        # Step 5: Create trigger for updated_at
        conn.execute(
            text("""
            DROP TRIGGER IF EXISTS trigger_agent_rewards_updated_at ON agent_daily_rewards;
            """)
        )
        conn.execute(
            text("""
            CREATE TRIGGER trigger_agent_rewards_updated_at
                BEFORE UPDATE ON agent_daily_rewards
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """)
        )

        # Step 6: Compute initial rewards from existing data
        print("Computing initial rewards from historical data...")

        # Get default weights ID
        weights_id = conn.execute(
            text("SELECT id FROM reward_weights WHERE name = 'business_focused'")
        ).scalar()

        result = conn.execute(
            text("""
            INSERT INTO agent_daily_rewards (
                agent_id, reward_date, reward_weights_id,
                profit_reward, satisfaction_reward, frequency_reward, diversity_reward,
                total_revenue, total_cost, total_profit, avg_discount_rate,
                days_since_last_purchase, unique_categories_count, total_reward
            )
            SELECT 
                ass.agent_id,
                ass.snapshot_date as reward_date,
                :weights_id as reward_weights_id,
                
                -- Profit reward: normalized profit margin (target 15%)
                CASE 
                    WHEN COALESCE(daily_orders.revenue, 0) > 0 
                    THEN ((daily_orders.profit / daily_orders.revenue) - 0.15) * 10.0
                    ELSE -0.5  -- Penalty for no purchase
                END as profit_reward,
                
                -- Satisfaction reward: based on discount received (up to 20% is good)
                CASE 
                    WHEN COALESCE(daily_orders.discount_rate, 0) <= 0.20 
                    THEN daily_orders.discount_rate * 5.0  -- Positive up to 1.0
                    ELSE (0.40 - daily_orders.discount_rate) * 5.0  -- Negative if > 40%
                END as satisfaction_reward,
                
                -- Frequency reward: good to purchase every 7 days
                CASE 
                    WHEN ass.days_since_last_purchase IS NULL THEN -0.3
                    WHEN ass.days_since_last_purchase <= 7 THEN 1.0 - (ass.days_since_last_purchase / 7.0)
                    WHEN ass.days_since_last_purchase <= 14 THEN -0.5 * ((ass.days_since_last_purchase - 7) / 7.0)
                    ELSE -1.0
                END as frequency_reward,
                
                -- Diversity reward: encourage exploring categories
                CASE 
                    WHEN ass.diversity_ratio >= 0.30 THEN 1.0
                    WHEN ass.diversity_ratio >= 0.15 THEN ass.diversity_ratio * 3.33
                    ELSE -0.5 + (ass.diversity_ratio * 3.33)
                END as diversity_reward,
                
                -- Raw metrics
                COALESCE(daily_orders.revenue, 0) as total_revenue,
                COALESCE(daily_orders.cost, 0) as total_cost,
                COALESCE(daily_orders.profit, 0) as total_profit,
                COALESCE(daily_orders.discount_rate, 0) as avg_discount_rate,
                ass.days_since_last_purchase,
                ass.categories_purchased_this_week as unique_categories_count,
                
                -- Weighted total
                (0.40 * CASE 
                    WHEN COALESCE(daily_orders.revenue, 0) > 0 
                    THEN ((daily_orders.profit / daily_orders.revenue) - 0.15) * 10.0
                    ELSE -0.5
                END) +
                (0.30 * CASE 
                    WHEN COALESCE(daily_orders.discount_rate, 0) <= 0.20 
                    THEN daily_orders.discount_rate * 5.0
                    ELSE (0.40 - daily_orders.discount_rate) * 5.0
                END) +
                (0.20 * CASE 
                    WHEN ass.days_since_last_purchase IS NULL THEN -0.3
                    WHEN ass.days_since_last_purchase <= 7 THEN 1.0 - (ass.days_since_last_purchase / 7.0)
                    WHEN ass.days_since_last_purchase <= 14 THEN -0.5 * ((ass.days_since_last_purchase - 7) / 7.0)
                    ELSE -1.0
                END) +
                (0.10 * CASE 
                    WHEN ass.diversity_ratio >= 0.30 THEN 1.0
                    WHEN ass.diversity_ratio >= 0.15 THEN ass.diversity_ratio * 3.33
                    ELSE -0.5 + (ass.diversity_ratio * 3.33)
                END) as total_reward
                
            FROM agent_state_snapshots ass
            LEFT JOIN (
                SELECT 
                    a.id as agent_id,
                    DATE(o.created_at) as order_date,
                    SUM(o.final_total) as revenue,
                    SUM(o.final_total * (1 - COALESCE(
                        (SELECT AVG(margin_percent) FROM products), 0.20
                    ))) as cost,
                    SUM(o.final_total * COALESCE(
                        (SELECT AVG(margin_percent) FROM products), 0.20
                    ) - (o.final_total - o.subtotal)) as profit,
                    CASE 
                        WHEN SUM(o.subtotal) > 0 
                        THEN (SUM(o.subtotal) - SUM(o.final_total)) / SUM(o.subtotal)
                        ELSE 0 
                    END as discount_rate
                FROM orders o
                JOIN agents a ON a.user_id = o.user_id
                WHERE o.is_simulated = true
                GROUP BY a.id, DATE(o.created_at)
            ) daily_orders ON daily_orders.agent_id = ass.agent_id 
                AND daily_orders.order_date = ass.snapshot_date
            
            ON CONFLICT (agent_id, reward_date, reward_weights_id)
            DO UPDATE SET
                profit_reward = EXCLUDED.profit_reward,
                satisfaction_reward = EXCLUDED.satisfaction_reward,
                frequency_reward = EXCLUDED.frequency_reward,
                diversity_reward = EXCLUDED.diversity_reward,
                total_revenue = EXCLUDED.total_revenue,
                total_cost = EXCLUDED.total_cost,
                total_profit = EXCLUDED.total_profit,
                avg_discount_rate = EXCLUDED.avg_discount_rate,
                days_since_last_purchase = EXCLUDED.days_since_last_purchase,
                unique_categories_count = EXCLUDED.unique_categories_count,
                total_reward = EXCLUDED.total_reward,
                updated_at = CURRENT_TIMESTAMP
            """),
            {"weights_id": weights_id},
        )

        rewards_count = result.rowcount
        print(f"Created/updated {rewards_count} reward records")

        conn.commit()

        # Validation
        reward_stats = conn.execute(
            text("""
            SELECT 
                COUNT(*) as total_records,
                AVG(total_reward) as avg_total_reward,
                MIN(total_reward) as min_reward,
                MAX(total_reward) as max_reward,
                AVG(profit_reward) as avg_profit,
                AVG(satisfaction_reward) as avg_satisfaction,
                AVG(frequency_reward) as avg_frequency,
                AVG(diversity_reward) as avg_diversity
            FROM agent_daily_rewards
            """)
        ).fetchone()

        print(f"\nValidation Results:")
        print(f"  - Total reward records: {reward_stats[0]}")
        print(f"  - Average total reward: {reward_stats[1]:.4f}")
        print(f"  - Reward range: [{reward_stats[2]:.4f}, {reward_stats[3]:.4f}]")
        print(f"\n  Component averages:")
        print(f"    - Profit: {reward_stats[4]:.4f}")
        print(f"    - Satisfaction: {reward_stats[5]:.4f}")
        print(f"    - Frequency: {reward_stats[6]:.4f}")
        print(f"    - Diversity: {reward_stats[7]:.4f}")

        # Weekly aggregation check
        weekly_stats = conn.execute(
            text("""
            SELECT 
                DATE_TRUNC('week', reward_date) as week,
                COUNT(*) as records,
                AVG(total_reward) as avg_reward
            FROM agent_daily_rewards
            GROUP BY DATE_TRUNC('week', reward_date)
            ORDER BY week
            LIMIT 5
            """)
        ).fetchall()

        print(f"\nWeekly reward aggregates (first 5 weeks):")
        for row in weekly_stats:
            week_date = row[0].date() if row[0] else "Unknown"
            record_count = row[1] if row[1] is not None else 0
            avg_reward = row[2] if row[2] is not None else 0.0
            print(
                f"  Week of {week_date}: {record_count} records, avg reward: {avg_reward:.4f}"
            )

        print("\n✅ Task 2.3 completed successfully!")

        return rewards_count


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Sprint 2: Daily State Snapshots + Rewards")
        print("=" * 60)

        # Run all migrations
        run_migration_001()
        run_migration_002()
        run_migration_003()

        print("\n" + "=" * 60)
        print("🎉 All Sprint 2 migrations completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error executing migrations: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
