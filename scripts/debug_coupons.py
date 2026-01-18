import sys
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:dev@localhost:5432/voiceoffers"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def debug_coupons(email):
    print(f"Connecting to: {DATABASE_URL}")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check NOW()
            res = conn.execute(text("SELECT NOW()"))
            print(f"DB NOW(): {res.scalar()}")

            # Get User ID
            res = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
            user_row = res.fetchone()
            if not user_row:
                print("User not found!")
                return
            user_id = str(user_row[0])

            # Specific Check for target coupons
            print("\n--- Specific Coupons Detail ---")
            query_specific = text("""
                SELECT c.id, c.discount_details, uc.status, uc.eligible_until, c.expiration_date, c.is_active
                FROM user_coupons uc
                JOIN coupons c ON uc.coupon_id = c.id
                WHERE uc.user_id = :user_id
                  AND (c.discount_details LIKE '%15% off orders over $50%' OR c.discount_details LIKE '%$25 off $125 purchase%')
            """)
            res = conn.execute(query_specific, {"user_id": user_id})
            for row in res.fetchall():
                 print(f"Desc: {row.discount_details}")
                 print(f"  UC Status: {row.status}")
                 print(f"  UC Eligible Until: {row.eligible_until}")
                 print(f"  C Expiration Date: {row.expiration_date}")
                 print(f"  C Is Active: {row.is_active}")
                 print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_coupons("unmeshmali@gmail.com")
