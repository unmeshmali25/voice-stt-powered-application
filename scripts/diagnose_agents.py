#!/usr/bin/env python3
"""
Diagnose agent status and provide actionable guidance.

Usage:
    python scripts/diagnose_agents.py
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def diagnose_agents():
    """Check agent status and provide guidance."""
    db_url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Check active agents
        active_count = conn.execute(
            text("SELECT COUNT(*) FROM agents WHERE is_active = true")
        ).scalar() or 0

        total_count = conn.execute(
            text("SELECT COUNT(*) FROM agents")
        ).scalar() or 0

        inactive_count = total_count - active_count

        print("=" * 60)
        print("AGENT DIAGNOSTIC REPORT")
        print("=" * 60)
        print(f"\nTotal agents:    {total_count}")
        print(f"Active agents:   {active_count} (is_active = true)")
        print(f"Inactive agents: {inactive_count} (is_active = false)")
        print(f"\nExpected:        2400 active agents")
        print()

        # Diagnosis
        if active_count == 0:
            print("❌ STATUS: CRITICAL - No agents available for simulation")
            print()
            print("CAUSE: Agents were likely deleted by running:")
            print("  - data/agent_validation/13_manual_cleanup.sql (lines 54-59)")
            print()
            print("TO FIX:")
            print("  1. Reseed all agents from Excel:")
            print("     python scripts/seed_simulation_agents.py data/personas/personas.xlsx")
            print()
            print("  2. Or create test agents quickly:")
            print("     python scripts/seed_simulation_agents.py --test")
            print()
        elif active_count < 2400:
            print(f"⚠️  STATUS: WARNING - Only {active_count/2400*100:.1f}% of expected agents")
            print()
            print("TO FIX:")
            print("  Reseed to restore full dataset:")
            print("  python scripts/seed_simulation_agents.py --force data/personas/personas.xlsx")
            print()
        else:
            print("✅ STATUS: OK - All agents available")
            print()
            # Show distribution
            model_dist = conn.execute(text("""
                SELECT generation_model, COUNT(*) as count
                FROM agents
                WHERE is_active = true
                GROUP BY generation_model
                ORDER BY count DESC
            """)).fetchall()

            if model_dist:
                print("Agent distribution by model:")
                for row in model_dist:
                    print(f"  - {row[0]}: {row[1]} agents")
                print()

        print("=" * 60)

if __name__ == "__main__":
    diagnose_agents()
