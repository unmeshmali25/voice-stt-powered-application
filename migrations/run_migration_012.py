#!/usr/bin/env python3
"""Execute migration 012: Fix llm_decisions schema."""

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


def run_migration_012():
    """Fix llm_decisions schema - add missing columns and fix urgency type."""
    print("\n=== Migration 012: Fix llm_decisions Schema ===")

    # Read the SQL file
    migration_path = os.path.join(
        os.path.dirname(__file__), "012_fix_llm_decisions_schema.sql"
    )

    with open(migration_path, "r") as f:
        sql_content = f.read()

    with engine.connect() as conn:
        # Check current schema
        print("  Checking current schema...")

        # Check if simulation_id exists
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'llm_decisions' 
                AND column_name = 'simulation_id'
            )
        """)
        ).fetchone()

        has_simulation_id = result and result[0]

        # Check if llm_provider exists
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'llm_decisions' 
                AND column_name = 'llm_provider'
            )
        """)
        ).fetchone()

        has_llm_provider = result and result[0]

        # Check urgency type
        result = conn.execute(
            text("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'llm_decisions' 
            AND column_name = 'urgency'
        """)
        ).fetchone()

        urgency_type = result[0] if result else None
        is_urgency_float = urgency_type in (
            "double precision",
            "real",
            "numeric",
            "float",
        )

        if has_simulation_id and has_llm_provider and is_urgency_float:
            print("  Schema is already up to date. Skipping...")
            conn.commit()
            return

        # Execute the migration
        print("  Applying schema fixes...")
        conn.execute(text(sql_content))
        conn.commit()

        # Verify changes
        print("  Verifying changes...")

        # Check simulation_id
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'llm_decisions' 
                AND column_name = 'simulation_id'
            )
        """)
        ).fetchone()

        if result and result[0]:
            print("  ✓ simulation_id column added")
        else:
            print("  ✗ simulation_id column was not added")
            sys.exit(1)

        # Check llm_provider
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'llm_decisions' 
                AND column_name = 'llm_provider'
            )
        """)
        ).fetchone()

        if result and result[0]:
            print("  ✓ llm_provider column added")
        else:
            print("  ✗ llm_provider column was not added")
            sys.exit(1)

        # Check urgency type
        result = conn.execute(
            text("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'llm_decisions' 
            AND column_name = 'urgency'
        """)
        ).fetchone()

        if result and result[0] in ("double precision", "real", "numeric", "float"):
            print(f"  ✓ urgency column type changed to {result[0]}")
        else:
            print(f"  ⚠ urgency column type is {result[0] if result else 'unknown'}")


if __name__ == "__main__":
    run_migration_012()
    print("\n✓ Migration 012 completed successfully!")
