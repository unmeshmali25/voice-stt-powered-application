"""
Backfill Script: Assign Coupons to Users

Assigns random coupons to all users who have fewer than 32 active coupons.
Each user gets:
- 2 frontstore coupons
- 30 category/brand coupons
- All expire in 14 days

Usage:
    python scripts/assign_coupons_to_users.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:dev@localhost:5432/voiceoffers")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Database engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def assign_random_coupons_to_user(db, user_id: str) -> int:
    """
    Assign random coupons to user's wallet.
    Returns: Number of coupons assigned
    """
    try:
        # Check current active coupon counts by type
        result = db.execute(
            text("""
                SELECT 
                    c.type,
                    COUNT(*) as count
                FROM user_coupons uc
                JOIN coupons c ON uc.coupon_id = c.id
                WHERE uc.user_id = :user_id
                  AND uc.eligible_until > NOW()
                GROUP BY c.type
            """),
            {"user_id": user_id}
        )
        
        current_counts = {row[0]: row[1] for row in result.fetchall()}
        frontstore_count = current_counts.get('frontstore', 0)
        category_brand_count = current_counts.get('category', 0) + current_counts.get('brand', 0)
        
        # Calculate how many coupons to assign
        frontstore_needed = max(0, 2 - frontstore_count)
        category_brand_needed = max(0, 30 - category_brand_count)
        
        total_assigned = 0
        
        # Assign frontstore coupons
        if frontstore_needed > 0:
            result = db.execute(
                text("""
                    SELECT id FROM coupons
                    WHERE type = 'frontstore'
                      AND expiration_date > NOW()
                      AND id NOT IN (
                          SELECT coupon_id FROM user_coupons WHERE user_id = :user_id
                      )
                    ORDER BY RANDOM()
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": frontstore_needed}
            )
            
            for row in result.fetchall():
                db.execute(
                    text("""
                        INSERT INTO user_coupons (user_id, coupon_id, eligible_until)
                        VALUES (:user_id, :coupon_id, NOW() + INTERVAL '14 days')
                        ON CONFLICT (user_id, coupon_id) DO NOTHING
                    """),
                    {"user_id": user_id, "coupon_id": row[0]}
                )
                total_assigned += 1
        
        # Assign category/brand coupons
        if category_brand_needed > 0:
            result = db.execute(
                text("""
                    SELECT id FROM coupons
                    WHERE type IN ('category', 'brand')
                      AND expiration_date > NOW()
                      AND id NOT IN (
                          SELECT coupon_id FROM user_coupons WHERE user_id = :user_id
                      )
                    ORDER BY RANDOM()
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": category_brand_needed}
            )
            
            for row in result.fetchall():
                db.execute(
                    text("""
                        INSERT INTO user_coupons (user_id, coupon_id, eligible_until)
                        VALUES (:user_id, :coupon_id, NOW() + INTERVAL '14 days')
                        ON CONFLICT (user_id, coupon_id) DO NOTHING
                    """),
                    {"user_id": user_id, "coupon_id": row[0]}
                )
                total_assigned += 1
        
        db.commit()
        
        if total_assigned > 0:
            print(f"  ✓ Assigned {total_assigned} coupons to user {user_id} ({frontstore_needed} frontstore, {category_brand_needed} category/brand)")
        
        return total_assigned
        
    except Exception as e:
        print(f"  ✗ Failed to assign coupons to user {user_id}: {e}")
        db.rollback()
        return 0


def main():
    print("=" * 70)
    print("Coupon Assignment Backfill Script")
    print("=" * 70)
    print()
    
    session = SessionLocal()
    
    try:
        # Fetch all users
        result = session.execute(
            text("SELECT id, email FROM users ORDER BY created_at")
        )
        users = result.fetchall()
        
        if not users:
            print("No users found in database.")
            return
        
        print(f"Found {len(users)} users in database")
        print()
        
        # Process each user
        total_users_processed = 0
        total_coupons_assigned = 0
        users_with_full_wallet = 0
        
        for user_id, email in users:
            # Check if user needs coupons
            result = session.execute(
                text("""
                    SELECT COUNT(*) FROM user_coupons
                    WHERE user_id = :user_id
                      AND eligible_until > NOW()
                """),
                {"user_id": user_id}
            )
            active_coupon_count = result.scalar() or 0
            
            if active_coupon_count >= 32:
                users_with_full_wallet += 1
                print(f"  → User {email} already has {active_coupon_count} active coupons (full wallet)")
                continue
            
            print(f"Processing user: {email} (current: {active_coupon_count} active coupons)")
            coupons_assigned = assign_random_coupons_to_user(session, str(user_id))
            
            if coupons_assigned > 0:
                total_users_processed += 1
                total_coupons_assigned += coupons_assigned
        
        print()
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total users in database: {len(users)}")
        print(f"Users with full wallet (32 coupons): {users_with_full_wallet}")
        print(f"Users processed (assigned coupons): {total_users_processed}")
        print(f"Total coupons assigned: {total_coupons_assigned}")
        print()
        print("Backfill complete!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\nError during backfill: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

