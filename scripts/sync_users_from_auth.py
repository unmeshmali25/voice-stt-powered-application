"""
Sync Users from Supabase auth.users to local users table

This script copies users from Supabase's auth.users table to the application's
users table, so they can receive coupon assignments.

Usage:
    python scripts/sync_users_from_auth.py
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


def sync_users_from_auth(db):
    """
    Sync users from auth.users table to users table.
    Returns: Number of users synced
    """
    try:
        # Check if auth.users table exists and is accessible
        try:
            result = db.execute(
                text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'auth' AND table_name = 'users'
                """)
            )
            auth_table_exists = result.scalar() > 0
            
            if not auth_table_exists:
                print("⚠️  auth.users table not found. This might be a Supabase database.")
                print("   Trying to access auth.users directly...")
        except Exception as e:
            print(f"⚠️  Could not check for auth.users table: {e}")
            print("   Attempting to sync anyway...")
        
        # Fetch users from auth.users table
        # Note: In Supabase, auth.users is in the auth schema
        try:
            result = db.execute(
                text("""
                    SELECT 
                        id,
                        email,
                        raw_user_meta_data->>'full_name' as full_name,
                        created_at
                    FROM auth.users
                    WHERE email IS NOT NULL
                    ORDER BY created_at
                """)
            )
            auth_users = result.fetchall()
        except Exception as e:
            # Try alternative query if the above fails
            try:
                result = db.execute(
                    text("""
                        SELECT 
                            id,
                            email,
                            COALESCE(raw_user_meta_data->>'full_name', raw_user_meta_data->>'name') as full_name,
                            created_at
                        FROM auth.users
                        WHERE email IS NOT NULL
                        ORDER BY created_at
                    """)
                )
                auth_users = result.fetchall()
            except Exception as e2:
                print(f"❌ Failed to query auth.users: {e2}")
                print("   Make sure you have access to the auth schema.")
                return 0
        
        if not auth_users:
            print("No users found in auth.users table.")
            return 0
        
        print(f"Found {len(auth_users)} users in auth.users table")
        print()
        
        # Sync each user to local users table
        synced_count = 0
        skipped_count = 0
        
        for user_id, email, full_name, created_at in auth_users:
            try:
                # Check if user already exists
                check_result = db.execute(
                    text("SELECT id FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                )
                
                if check_result.fetchone():
                    print(f"  ⊘ User {email} already exists, skipping")
                    skipped_count += 1
                    continue
                
                # Insert user into local users table
                db.execute(
                    text("""
                        INSERT INTO users (id, email, full_name, created_at)
                        VALUES (:id, :email, :full_name, :created_at)
                        ON CONFLICT (id) DO UPDATE SET
                            email = EXCLUDED.email,
                            full_name = EXCLUDED.full_name,
                            updated_at = CURRENT_TIMESTAMP
                    """),
                    {
                        "id": user_id,
                        "email": email,
                        "full_name": full_name,
                        "created_at": created_at
                    }
                )
                synced_count += 1
                print(f"  ✓ Synced user: {email}")
                
            except Exception as e:
                print(f"  ✗ Failed to sync user {email}: {e}")
                continue
        
        db.commit()
        
        print()
        print(f"Successfully synced {synced_count} users")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} users (already exist)")
        
        return synced_count
        
    except Exception as e:
        print(f"❌ Error syncing users: {e}")
        db.rollback()
        return 0


def main():
    print("=" * 70)
    print("Sync Users from Supabase auth.users to local users table")
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
        synced_count = sync_users_from_auth(session)
        
        if synced_count > 0:
            print()
            print("=" * 70)
            print("✅ User sync complete!")
            print("=" * 70)
            print()
            print("Next step: Run the coupon assignment script:")
            print("  python scripts/assign_coupons_to_users.py")
        else:
            print()
            print("=" * 70)
            print("ℹ️  No new users to sync")
            print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

