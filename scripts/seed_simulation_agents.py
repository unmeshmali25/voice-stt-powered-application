#!/usr/bin/env python3
"""
Agent Seeding Script - S-3

Seeds agents from persona Excel file into the database.
Creates both user entries and agent entries with all 28 structured columns.

Usage:
    python scripts/seed_simulation_agents.py data/personas/personas.xlsx
    python scripts/seed_simulation_agents.py --test  # Create 2 test agents
    python scripts/seed_simulation_agents.py data/personas/personas.xlsx --count 2
"""

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qsl, urlencode, unquote

# Load environment variables from .env files
from dotenv import load_dotenv

# Try loading .env.production first, then .env
env_prod = Path(__file__).parent.parent / ".env.production"
env_dev = Path(__file__).parent.parent / ".env"
if env_prod.exists():
    load_dotenv(env_prod)
    print(f"Loaded environment from {env_prod}")
elif env_dev.exists():
    load_dotenv(env_dev)
    print(f"Loaded environment from {env_dev}")

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from environment, properly handling special characters in password."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable not set")

    # Robustly handle special characters in DB credentials by URL-encoding them
    try:
        parsed_db_url = urlparse(url)
        # Only rebuild if we have a recognizable netloc and scheme
        if parsed_db_url.scheme and parsed_db_url.netloc:
            username = parsed_db_url.username or ""
            password = parsed_db_url.password or ""
            host = parsed_db_url.hostname or ""
            port = parsed_db_url.port

            # Encode username/password to safely handle characters like '@', ':', etc.
            if username or password:
                encoded_username = quote_plus(unquote(username))
                encoded_password = quote_plus(unquote(password))
                netloc = f"{encoded_username}:{encoded_password}@{host}"
            else:
                netloc = host

            if port:
                netloc += f":{port}"

            # Ensure sslmode=require for hosted providers (e.g., Supabase)
            query_params = dict(parse_qsl(parsed_db_url.query, keep_blank_values=True))
            query_params.setdefault("sslmode", "require")

            url = urlunparse(
                (
                    parsed_db_url.scheme,
                    netloc,
                    parsed_db_url.path,
                    parsed_db_url.params,
                    urlencode(query_params),
                    parsed_db_url.fragment,
                )
            )
            logger.info(f"Database URL processed (credentials encoded)")
            logger.debug(
                f"Username: {username}, Password length: {len(password)}, Host: {host}"
            )
    except Exception as e:
        logger.warning(f"Failed to process database URL: {e}, using original")
        # If anything goes wrong, fall back to the original DATABASE_URL
        pass

    return url


def create_test_agents(session, count: int = 2):
    """Create test agents for quick testing."""
    test_agents = [
        {
            "agent_id": "agent_001",
            "age": 28,
            "age_group": "25-34",
            "gender": "female",
            "income_bracket": "medium",
            "household_size": 2,
            "has_children": False,
            "location_region": "Pacific Northwest",
            "price_sensitivity": 0.75,
            "brand_loyalty": 0.40,
            "impulsivity": 0.30,
            "tech_savviness": 0.85,
            "preferred_categories": "Wellness, Skincare, Supplements",
            "weekly_budget": 75.00,
            "shopping_frequency": "regular",
            "avg_cart_value": 45.00,
            "pref_day_weekday": 0.60,
            "pref_day_saturday": 0.85,
            "pref_day_sunday": 0.40,
            "pref_time_morning": 0.20,
            "pref_time_afternoon": 0.50,
            "pref_time_evening": 0.80,
            "coupon_affinity": 0.85,
            "deal_seeking_behavior": "active_hunter",
            "backstory": "Sarah is a health-conscious millennial who loves finding deals on wellness products.",
            "sample_shopping_patterns": "Weekly vitamin runs|Weekend skincare hauls|Flash sale hunter",
        },
        {
            "agent_id": "agent_002",
            "age": 45,
            "age_group": "45-54",
            "gender": "male",
            "income_bracket": "high",
            "household_size": 4,
            "has_children": True,
            "location_region": "Midwest",
            "price_sensitivity": 0.35,
            "brand_loyalty": 0.80,
            "impulsivity": 0.20,
            "tech_savviness": 0.55,
            "preferred_categories": "Household, Baby Care, Personal Care",
            "weekly_budget": 150.00,
            "shopping_frequency": "frequent",
            "avg_cart_value": 85.00,
            "pref_day_weekday": 0.75,
            "pref_day_saturday": 0.60,
            "pref_day_sunday": 0.30,
            "pref_time_morning": 0.70,
            "pref_time_afternoon": 0.40,
            "pref_time_evening": 0.20,
            "coupon_affinity": 0.50,
            "deal_seeking_behavior": "passive",
            "backstory": "Mike is a busy dad who values convenience and sticks to trusted brands.",
            "sample_shopping_patterns": "Morning quick stops|Bulk family purchases|Monthly stock-ups",
        },
    ]

    for agent_data in test_agents[:count]:
        seed_single_agent(session, agent_data, auto_commit=False)

    # Commit all test agents at once (only 2-3 agents)
    session.commit()
    logger.info(f"Created {count} test agents")


def seed_single_agent(
    session, agent_data: dict, force: bool = False, auto_commit: bool = True
):
    """Seed a single agent into the database.

    Args:
        session: Database session
        agent_data: Agent data dictionary
        force: Whether to delete existing agents
        auto_commit: Whether to commit after insert (default True for backward compatibility)
    """
    agent_id = agent_data.get("agent_id")

    # Check if agent already exists
    existing = session.execute(
        text("SELECT id, user_id FROM agents WHERE agent_id = :aid"), {"aid": agent_id}
    ).fetchone()

    if existing:
        if force:
            # Delete existing agent and user
            logger.info(f"Force mode: Deleting existing agent {agent_id}")
            session.execute(
                text("DELETE FROM agents WHERE agent_id = :aid"), {"aid": agent_id}
            )
            session.execute(
                text("DELETE FROM users WHERE id = :uid"), {"uid": existing.user_id}
            )
            session.commit()
        else:
            logger.info(
                f"Agent {agent_id} already exists, skipping (use --force to overwrite)"
            )
            return

    user_id = str(uuid.uuid4())

    # Create user entry
    session.execute(
        text("""
        INSERT INTO users (id, email, full_name, created_at)
        VALUES (:id, :email, :name, NOW())
        ON CONFLICT (id) DO NOTHING
    """),
        {
            "id": user_id,
            "email": f"{agent_id}@simulation.local",
            "name": f"Agent {agent_id}",
        },
    )

    # Create agent entry with all columns
    session.execute(
        text("""
        INSERT INTO agents (
            agent_id, user_id, generation_model, generated_at,
            age, age_group, gender, income_bracket, household_size, has_children, location_region,
            price_sensitivity, brand_loyalty, impulsivity, tech_savviness,
            preferred_categories, weekly_budget, shopping_frequency, avg_cart_value,
            pref_day_weekday, pref_day_saturday, pref_day_sunday,
            pref_time_morning, pref_time_afternoon, pref_time_evening,
            coupon_affinity, deal_seeking_behavior, backstory, sample_shopping_patterns,
            is_active, created_at
        ) VALUES (
            :agent_id, :user_id, :generation_model, NOW(),
            :age, :age_group, :gender, :income_bracket, :household_size, :has_children, :location_region,
            :price_sensitivity, :brand_loyalty, :impulsivity, :tech_savviness,
            :preferred_categories, :weekly_budget, :shopping_frequency, :avg_cart_value,
            :pref_day_weekday, :pref_day_saturday, :pref_day_sunday,
            :pref_time_morning, :pref_time_afternoon, :pref_time_evening,
            :coupon_affinity, :deal_seeking_behavior, :backstory, :sample_shopping_patterns,
            true, NOW()
        )
    """),
        {
            "agent_id": agent_id,
            "user_id": user_id,
            "generation_model": agent_data.get("generation_model", "test"),
            "age": agent_data.get("age"),
            "age_group": agent_data.get("age_group"),
            "gender": agent_data.get("gender"),
            "income_bracket": agent_data.get("income_bracket"),
            "household_size": agent_data.get("household_size"),
            "has_children": agent_data.get("has_children", False),
            "location_region": agent_data.get("location_region"),
            "price_sensitivity": agent_data.get("price_sensitivity"),
            "brand_loyalty": agent_data.get("brand_loyalty"),
            "impulsivity": agent_data.get("impulsivity"),
            "tech_savviness": agent_data.get("tech_savviness"),
            "preferred_categories": agent_data.get("preferred_categories"),
            "weekly_budget": agent_data.get("weekly_budget"),
            "shopping_frequency": agent_data.get("shopping_frequency"),
            "avg_cart_value": agent_data.get("avg_cart_value"),
            "pref_day_weekday": agent_data.get("pref_day_weekday"),
            "pref_day_saturday": agent_data.get("pref_day_saturday"),
            "pref_day_sunday": agent_data.get("pref_day_sunday"),
            "pref_time_morning": agent_data.get("pref_time_morning"),
            "pref_time_afternoon": agent_data.get("pref_time_afternoon"),
            "pref_time_evening": agent_data.get("pref_time_evening"),
            "coupon_affinity": agent_data.get("coupon_affinity"),
            "deal_seeking_behavior": agent_data.get("deal_seeking_behavior"),
            "backstory": agent_data.get("backstory"),
            "sample_shopping_patterns": agent_data.get("sample_shopping_patterns"),
        },
    )

    if auto_commit:
        session.commit()
    logger.info(f"Created agent {agent_id} with user_id {user_id}")


def seed_from_excel(
    session, excel_path: str, count: Optional[int] = None, force: bool = False
):
    """Seed agents from persona Excel or JSON file."""
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"File not found: {excel_path}")

    # Check if it's a JSON file
    if excel_path.endswith(".json"):
        import json

        with open(excel_path, "r") as f:
            data = json.load(f)
        personas = data.get("personas", [])
        logger.info(f"Found {len(personas)} personas in JSON file")
    else:
        # Read from "All Attributes" sheet as base
        try:
            df = pd.read_excel(excel_path, sheet_name="All Attributes")
            logger.info(f"Read {len(df)} rows from 'All Attributes' sheet")
        except ValueError:
            df = pd.read_excel(excel_path, sheet_name=0)
            logger.warning("'All Attributes' sheet not found, using first sheet")

        # Merge backstory from "Backstories" sheet
        try:
            backstories_df = pd.read_excel(excel_path, sheet_name="Backstories")
            # Rename columns to match our schema
            backstories_df = backstories_df.rename(
                columns={"Agent ID": "agent_id", "Backstory": "backstory"}
            )
            backstories_df = backstories_df[["agent_id", "backstory"]]
            df = df.merge(backstories_df, on="agent_id", how="left")
            logger.info(f"Merged backstories from 'Backstories' sheet")
        except Exception as e:
            logger.warning(f"Could not merge backstories: {e}")

        # Merge shopping patterns from "Shopping Patterns" sheet
        try:
            patterns_df = pd.read_excel(excel_path, sheet_name="Shopping Patterns")
            # Rename columns to match our schema
            patterns_df = patterns_df.rename(
                columns={
                    "Agent ID": "agent_id",
                    "Shopping Patterns": "sample_shopping_patterns",
                }
            )
            patterns_df = patterns_df[["agent_id", "sample_shopping_patterns"]]
            df = df.merge(patterns_df, on="agent_id", how="left")
            logger.info(f"Merged shopping patterns from 'Shopping Patterns' sheet")
        except Exception as e:
            logger.warning(f"Could not merge shopping patterns: {e}")

        personas = df.to_dict("records")
        logger.info(f"Found {len(personas)} personas in Excel file (with merged data)")

    # Limit count if specified
    if count and count < len(personas):
        personas = personas[:count]
        logger.info(f"Limiting to first {count} personas")

    seeded_count = 0
    batch_size = 50  # Commit every 50 agents to avoid overwhelming connection pooler

    for idx, agent_data in enumerate(personas):
        try:
            # Don't auto-commit - we'll batch commit
            seed_single_agent(session, agent_data, force=force, auto_commit=False)
            seeded_count += 1

            # Commit every batch_size agents
            if (idx + 1) % batch_size == 0:
                session.commit()
                logger.info(
                    f"Progress: Seeded {seeded_count}/{len(personas)} agents (committed batch)"
                )
        except Exception as e:
            logger.error(f"Failed to seed agent {agent_data.get('agent_id')}: {e}")
            session.rollback()

    # Final commit for remaining agents
    if seeded_count % batch_size != 0:
        session.commit()
        logger.info(f"Final commit: Seeded {seeded_count} agents total")

    logger.info(f"Finished seeding {seeded_count} agents from {excel_path}")


def main():
    parser = argparse.ArgumentParser(description="Seed simulation agents into database")
    parser.add_argument(
        "file_path", nargs="?", help="Path to persona Excel or JSON file"
    )
    parser.add_argument(
        "--test", action="store_true", help="Create test agents from hardcoded data"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of agents to seed (default: all)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Delete and recreate existing agents"
    )

    args = parser.parse_args()

    # Connect to database
    database_url = get_database_url()
    logger.info(f"Connecting to database...")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        if args.test:
            count = args.count if args.count else 2
            create_test_agents(session, count)
        elif args.file_path:
            seed_from_excel(session, args.file_path, args.count, force=args.force)
        else:
            parser.print_help()
            sys.exit(1)

        logger.info("Agent seeding completed successfully")
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
