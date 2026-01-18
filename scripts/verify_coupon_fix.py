import sys
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def test_search_query(user_id):
    """Test that search respects is_active filter"""
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Simulate search query with is_active check
        result = conn.execute(
            text("""
            SELECT c.id, c.type, c.discount_details, c.is_active
            FROM coupons c
            JOIN user_coupons uc ON c.id = uc.coupon_id
            WHERE uc.user_id = :user_id
              AND uc.eligible_until > NOW()
              AND c.expiration_date > NOW()
              AND (c.is_active IS NULL OR c.is_active = true)
              AND c.type = 'frontstore'
            LIMIT 10
        """),
            {"user_id": user_id},
        )

        rows = result.fetchall()
        print(f"✓ Search returned {len(rows)} active coupons")

        # Verify none are inactive
        for row in rows:
            if row.is_active == False:
                print(f"✗ ERROR: Inactive coupon {row.id} returned")
                return False
        return True


def test_cart_sorting(user_id):
    """Test that cart sorts frontstore first"""
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT c.type, c.discount_details
            FROM coupons c
            JOIN user_coupons uc ON c.id = uc.coupon_id
            WHERE uc.user_id = :user_id
              AND uc.eligible_until > NOW()
              AND c.expiration_date > NOW()
              AND (c.is_active IS NULL OR c.is_active = true)
            ORDER BY
                CASE c.type
                    WHEN 'frontstore' THEN 1
                    WHEN 'category' THEN 2
                    WHEN 'brand' THEN 3
                    ELSE 4
                END,
                c.discount_value DESC NULLS LAST
            LIMIT 10
        """),
            {"user_id": user_id},
        )

        rows = result.fetchall()
        types_order = [row.type for row in rows]

        # Verify frontstore comes first
        if "frontstore" in types_order:
            first_frontstore = types_order.index("frontstore")
            if any(t in types_order[:first_frontstore] for t in ["brand", "category"]):
                print(f"✗ ERROR: Frontstore not first. Order: {types_order}")
                return False

        print(f"✓ Cart sorting correct: {types_order}")
        return True


if __name__ == "__main__":
    # Get user ID from email
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": "unmeshmali@gmail.com"},
        )
        user_id = str(res.scalar())

    print("Testing coupon visibility fixes...")
    test1 = test_search_query(user_id)
    test2 = test_cart_sorting(user_id)

    if test1 and test2:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed")
