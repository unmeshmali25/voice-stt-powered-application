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
import socket
from pathlib import Path
from urllib.parse import urlparse, urlunparse, quote_plus, parse_qsl, urlencode
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

# Robustly handle special characters in DB credentials by URL-encoding them
try:
    parsed_db_url = urlparse(DATABASE_URL)
    # Only rebuild if we have a recognizable netloc and scheme
    if parsed_db_url.scheme and parsed_db_url.netloc:
        username = parsed_db_url.username or ""
        password = parsed_db_url.password or ""
        host = parsed_db_url.hostname or ""
        port = parsed_db_url.port

        # Encode username/password to safely handle characters like '@', ':', etc.
        if username or password:
            encoded_username = quote_plus(username)
            encoded_password = quote_plus(password)
            netloc = f"{encoded_username}:{encoded_password}@{host}"
        else:
            netloc = host

        if port:
            netloc += f":{port}"

        # Ensure sslmode=require for hosted providers (e.g., Supabase)
        # Only require SSL for non-localhost connections
        query_params = dict(parse_qsl(parsed_db_url.query, keep_blank_values=True))
        if host not in {"localhost", "127.0.0.1"}:
            query_params.setdefault("sslmode", "require")

        # Prefer IPv4 if available to avoid IPv6-only connectivity issues on some hosts
        try:
            if host not in {"localhost", "127.0.0.1"}:
                addr_info_list = socket.getaddrinfo(host, port or 5432, socket.AF_INET, socket.SOCK_STREAM)
                if addr_info_list:
                    ipv4_addr = addr_info_list[0][4][0]
                    # Provide hostaddr while keeping host for TLS/SNI
                    query_params.setdefault("hostaddr", ipv4_addr)
        except Exception:
            # If DNS resolution fails, continue without hostaddr
            pass

        DATABASE_URL = urlunparse(
            (
                parsed_db_url.scheme,
                netloc,
                parsed_db_url.path,
                parsed_db_url.params,
                urlencode(query_params),
                parsed_db_url.fragment,
            )
        )
except Exception:
    # If anything goes wrong, fall back to the original DATABASE_URL
    pass

    # Database engine
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import sync function
    try:
        from sync_users_from_auth import sync_users_from_auth
    except ImportError:
        # If running from scripts directory
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from sync_users_from_auth import sync_users_from_auth




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
    
    # Check if DATABASE_URL is set (not using default localhost)
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "localhost" in db_url or "127.0.0.1" in db_url:
        print("⚠️  WARNING: DATABASE_URL not set or using localhost!")
        print("   Please set DATABASE_URL environment variable to your staging database.")
        print("   Example: export DATABASE_URL='postgresql://user:pass@host:5432/dbname'")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    session = SessionLocal()
    
    try:
        # Always try to sync users first to ensure we have the latest from auth.users
        print("Syncing users from auth.users...")
        try:
            sync_users_from_auth(session)
        except Exception as e:
            print(f"Warning: Sync failed: {e}")
            print("Continuing with existing users...")

        # Fetch all users
        result = session.execute(
            text("SELECT id, email FROM users ORDER BY created_at")
        )
        users = result.fetchall()
        
        if not users:
            print("⚠️  No users found in local users table even after sync.")
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

