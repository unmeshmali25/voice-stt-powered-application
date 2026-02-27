#!/usr/bin/env python3
"""Execute migration 011: Add llm_decisions table."""

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


def run_migration_011():
    """Create llm_decisions table for tracking LLM-based decisions."""
    print("\n=== Migration 011: Add llm_decisions Table ===")

    # Read the SQL file
    migration_path = os.path.join(
        os.path.dirname(__file__), "011_add_llm_decisions_table.sql"
    )

    with open(migration_path, "r") as f:
        sql_content = f.read()

    with engine.connect() as conn:
        # Check if table already exists
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'llm_decisions'
            )
        """)
        ).fetchone()

        if result and result[0]:
            print("  Table 'llm_decisions' already exists. Skipping...")
            conn.commit()
            return

        # Execute the migration
        print("  Creating llm_decisions table...")
        conn.execute(text(sql_content))
        conn.commit()

        # Verify table was created
        verify = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'llm_decisions'
            )
        """)
        ).fetchone()

        if verify and verify[0]:
            print("  ✓ Table created successfully")
        else:
            print("  ✗ Failed to create table")
            sys.exit(1)


if __name__ == "__main__":
    run_migration_011()
    print("\n✓ Migration 011 completed successfully!")
