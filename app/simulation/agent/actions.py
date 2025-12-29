"""
Shopping action executor for LangGraph simulation.

This module provides database operations for shopping behavior:
- Creating shopping sessions
- Browsing and viewing products
- Adding items to cart
- Viewing and applying coupons
- Completing or abandoning checkout
"""

import uuid
import json
import random
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def calculate_discount(coupon: Dict, amount: Decimal) -> Decimal:
    """
    Calculate discount amount based on coupon type.
    Matches real app coupon calculation logic.
    """
    discount_type = coupon.get("discount_type")
    discount_value = coupon.get("discount_value", Decimal("0"))
    max_discount = coupon.get("max_discount")

    if discount_type == "percent":
        discount = amount * (discount_value / Decimal("100"))
        if max_discount:
            discount = min(discount, max_discount)
        return discount
    elif discount_type == "fixed":
        return min(discount_value, amount)
    elif discount_type == "bogo":
        half_amount = amount / 2
        discount = half_amount * (discount_value / Decimal("100"))
        return discount
    elif discount_type == "free_shipping":
        return Decimal("0")
    return Decimal("0")


class ShoppingActions:
    """
    Executes shopping actions and records them in the database.

    All actions create appropriate shopping_session_events records
    for ML training data generation.
    """

    def __init__(self, db: Session):
        """
        Initialize with database session.

        Args:
            db: SQLAlchemy Session instance
        """
        self.db = db

    def add_to_cart_table(
        self,
        user_id: str,
        store_id: str,
        product_id: str,
        product_name: str,
        price: float,
        quantity: int,
    ) -> None:
        """
        Add item to cart_items table (persistent storage).
        Matches real app cart behavior.
        """
        self.db.execute(
            text("""
                INSERT INTO cart_items (user_id, store_id, product_id, quantity)
                VALUES (:user_id, :store_id, :product_id, :quantity)
                ON CONFLICT (user_id, store_id, product_id)
                DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
            """),
            {
                "user_id": user_id,
                "store_id": store_id,
                "product_id": product_id,
                "quantity": quantity,
            },
        )

    def add_coupon_to_cart(self, user_id: str, coupon_id: str) -> None:
        """
        Add coupon to cart_coupons table.
        Matches real app coupon selection behavior.
        """
        self.db.execute(
            text("""
                INSERT INTO cart_coupons (user_id, coupon_id)
                VALUES (:user_id, :coupon_id)
                ON CONFLICT (user_id, coupon_id) DO NOTHING
            """),
            {"user_id": user_id, "coupon_id": coupon_id},
        )

    def get_eligible_coupons(self, user_id: str, cart_items: List[dict]) -> List[dict]:
        """
        Get all user's coupons (eligibility checked in shopping_graph).
        Returns: List of coupon dictionaries
        """
        result = self.db.execute(
            text("""
                SELECT c.id, c.type, c.discount_details, c.category_or_brand,
                       c.discount_type, c.discount_value, c.min_purchase_amount, c.max_discount
                FROM coupons c
                JOIN user_coupons uc ON c.id = uc.coupon_id
                WHERE uc.user_id = :user_id
                  AND uc.eligible_until > NOW()
                  AND c.expiration_date > NOW()
            """),
            {"user_id": user_id},
        )

        coupons = []
        for row in result.fetchall():
            coupon = {
                "id": str(row[0]),
                "type": row[1],
                "discount_details": row[2],
                "category_or_brand": (row[3] or "").lower(),
                "discount_type": row[4],
                "discount_value": Decimal(str(row[5])) if row[5] else Decimal("0"),
                "min_purchase_amount": Decimal(str(row[6])) if row[6] else Decimal("0"),
                "max_discount": Decimal(str(row[7])) if row[7] else None,
            }
            coupons.append(coupon)

        return coupons

    def create_session(
        self, user_id: str, store_id: str, simulated_timestamp: datetime
    ) -> str:
        """
        Create a new shopping session.

        Args:
            user_id: User UUID
            store_id: Store UUID
            simulated_timestamp: Simulated datetime for the session

        Returns:
            Session ID (UUID string)
        """
        session_id = str(uuid.uuid4())

        self.db.execute(
            text("""
            INSERT INTO shopping_sessions
            (id, user_id, store_id, started_at, status, is_simulated)
            VALUES (:id, :user_id, :store_id, :started_at, 'active', true)
        """),
            {
                "id": session_id,
                "user_id": user_id,
                "store_id": store_id,
                "started_at": simulated_timestamp,
            },
        )

        logger.debug(f"Created session {session_id[:8]}... for user {user_id[:8]}...")
        return session_id

    def browse_products(
        self,
        session_id: str,
        user_id: str,
        preferred_categories: List[str],
        simulated_timestamp: datetime,
        max_products: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Browse products based on category preferences.
        Creates view_product events for each viewed product.

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            preferred_categories: List of preferred category names
            simulated_timestamp: Simulated datetime
            max_products: Maximum products to view

        Returns:
            List of product dictionaries with id, name, price, category
        """
        products = []

        # Select products - prioritize preferred categories if available
        if preferred_categories:
            # First try to get products from preferred categories
            result = self.db.execute(
                text("""
                SELECT id, name, price, category, brand
                FROM products
                WHERE in_stock = true
                AND LOWER(category) = ANY(ARRAY[:categories])
                ORDER BY RANDOM()
                LIMIT :limit
            """),
                {
                    "categories": [c.lower() for c in preferred_categories],
                    "limit": max_products,
                },
            )
            rows = result.fetchall()

            # If not enough, supplement with random products
            if len(rows) < max_products:
                remaining = max_products - len(rows)
                seen_ids = [str(row[0]) for row in rows]

                supplement = self.db.execute(
                    text("""
                    SELECT id, name, price, category, brand
                    FROM products
                    WHERE in_stock = true
                    AND id NOT IN (SELECT unnest(ARRAY[:seen_ids]::uuid[]))
                    ORDER BY RANDOM()
                    LIMIT :limit
                """),
                    {
                        "seen_ids": seen_ids
                        if seen_ids
                        else ["00000000-0000-0000-0000-000000000000"],
                        "limit": remaining,
                    },
                )
                rows = list(rows) + list(supplement.fetchall())
        else:
            # No preference - random selection
            result = self.db.execute(
                text("""
                SELECT id, name, price, category, brand
                FROM products
                WHERE in_stock = true
                ORDER BY RANDOM()
                LIMIT :limit
            """),
                {"limit": max_products},
            )
            rows = result.fetchall()

        # Record view events for each product
        for row in rows:
            product = {
                "id": str(row[0]),
                "name": row[1],
                "price": float(row[2]) if row[2] else 0.0,
                "category": row[3],
                "brand": row[4],
            }
            products.append(product)

            # Create view_product event
            self._record_event(
                session_id=session_id,
                user_id=user_id,
                event_type="view_product",
                payload={
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "price": product["price"],
                    "category": product["category"],
                },
                timestamp=simulated_timestamp,
            )

        logger.debug(f"Session {session_id[:8]}...: Viewed {len(products)} products")
        return products

    def add_to_cart(
        self,
        session_id: str,
        user_id: str,
        store_id: str,
        product_id: str,
        product_name: str,
        price: float,
        quantity: int,
        simulated_timestamp: datetime,
    ) -> None:
        """
        Add product to cart and record event.

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            store_id: Store UUID
            product_id: Product UUID
            product_name: Product name for event payload
            price: Product price
            quantity: Quantity to add
            simulated_timestamp: Simulated datetime
        """
        # Persist to cart_items table
        self.add_to_cart_table(
            user_id, store_id, product_id, product_name, price, quantity
        )

        # Create cart_add_item event
        self._record_event(
            session_id=session_id,
            user_id=user_id,
            event_type="cart_add_item",
            payload={
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "quantity": quantity,
            },
            timestamp=simulated_timestamp,
        )

        logger.debug(
            f"Session {session_id[:8]}...: Added {product_name} x{quantity} to cart"
        )

    def view_coupons(
        self, session_id: str, user_id: str, simulated_timestamp: datetime
    ) -> List[Dict[str, Any]]:
        """
        View available coupons for user.
        Creates coupon_view event.

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            simulated_timestamp: Simulated datetime

        Returns:
            List of available coupon dictionaries
        """
        # Get active coupons from user's wallet
        result = self.db.execute(
            text("""
            SELECT c.id, c.type, c.discount_details, c.category_or_brand, c.terms
            FROM user_coupons uc
            JOIN coupons c ON uc.coupon_id = c.id
            WHERE uc.user_id = :user_id
              AND (uc.status = 'active' OR uc.status IS NULL)
              AND uc.eligible_until > :now
        """),
            {"user_id": user_id, "now": simulated_timestamp},
        )

        coupons = []
        for row in result.fetchall():
            coupons.append(
                {
                    "id": str(row[0]),
                    "type": row[1],
                    "discount_details": row[2],
                    "category_or_brand": row[3],
                    "terms": row[4],
                }
            )

        # Record coupon view event
        self._record_event(
            session_id=session_id,
            user_id=user_id,
            event_type="view_coupons",
            payload={
                "coupon_count": len(coupons),
                "coupon_types": list(set(c["type"] for c in coupons)),
            },
            timestamp=simulated_timestamp,
        )

        logger.debug(f"Session {session_id[:8]}...: Viewed {len(coupons)} coupons")
        return coupons

    def apply_coupon(
        self,
        session_id: str,
        user_id: str,
        coupon_id: str,
        discount_details: str,
        simulated_timestamp: datetime,
    ) -> None:
        """
        Apply coupon to cart.

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            coupon_id: Coupon UUID to apply
            discount_details: Description of the discount
            simulated_timestamp: Simulated datetime
        """
        # Persist to cart_coupons table
        self.add_coupon_to_cart(user_id, coupon_id)

        # Record coupon_apply event
        self._record_event(
            session_id=session_id,
            user_id=user_id,
            event_type="coupon_apply",
            payload={"coupon_id": coupon_id, "discount_details": discount_details},
            timestamp=simulated_timestamp,
        )

        logger.debug(f"Session {session_id[:8]}...: Applied coupon {coupon_id[:8]}...")

    def complete_checkout(
        self,
        session_id: str,
        user_id: str,
        store_id: str,
        simulated_timestamp: datetime,
    ) -> Optional[str]:
        """
        Complete checkout with proper coupon application (matching real app).
        NO inventory checks - assumes all items available.

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            store_id: Store UUID
            simulated_timestamp: Simulated datetime

        Returns:
            Order ID (UUID string) or None if cart empty
        """
        # 1. Get cart items from database (no inventory join)
        items_result = self.db.execute(
            text("""
                SELECT ci.id, ci.quantity, p.id as product_id, p.name, p.price,
                       p.category, p.brand
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.user_id = :user_id AND ci.store_id = :store_id
            """),
            {"user_id": user_id, "store_id": store_id},
        )
        cart_items = items_result.fetchall()

        if not cart_items:
            # No items - abandon instead
            self.abandon_session(session_id, user_id, [], 0.0, simulated_timestamp)
            return None

        # 2. Get coupons from cart_coupons
        coupons_result = self.db.execute(
            text("""
                SELECT c.id, c.type, c.discount_details, c.category_or_brand,
                       c.discount_type, c.discount_value, c.min_purchase_amount, c.max_discount
                FROM cart_coupons cc
                JOIN coupons c ON cc.coupon_id = c.id
                WHERE cc.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        coupons = coupons_result.fetchall()

        # 3. Separate coupons by type
        frontstore_coupons = []
        category_coupons = []
        brand_coupons = []

        for c in coupons:
            coupon_data = {
                "id": str(c[0]),
                "type": c[1],
                "discount_details": c[2],
                "category_or_brand": (c[3] or "").lower(),
                "discount_type": c[4],
                "discount_value": Decimal(str(c[5])) if c[5] else Decimal("0"),
                "min_purchase_amount": Decimal(str(c[6])) if c[6] else Decimal("0"),
                "max_discount": Decimal(str(c[7])) if c[7] else None,
            }
            if c[1] == "frontstore":
                frontstore_coupons.append(coupon_data)
            elif c[1] == "category":
                category_coupons.append(coupon_data)
            elif c[1] == "brand":
                brand_coupons.append(coupon_data)

        # 4. Calculate totals and prepare order items
        subtotal = Decimal("0")
        order_items_data = []
        item_discount_total = Decimal("0")
        categories_with_discount = set()
        applied_coupon_ids = set()

        for item in cart_items:
            quantity = item[1]
            product_id = str(item[2])
            product_name = item[3]
            unit_price = Decimal(str(item[4])) if item[4] else Decimal("0")
            category = (item[5] or "").lower()
            brand = (item[6] or "").lower()
            line_total = unit_price * quantity
            subtotal += line_total

            # Find best applicable coupon
            best_discount = Decimal("0")
            best_coupon_id = None

            for coupon in category_coupons:
                if (
                    coupon["category_or_brand"] == category
                    and category not in categories_with_discount
                ):
                    discount = calculate_discount(coupon, line_total)
                    if discount > best_discount:
                        best_discount = discount
                        best_coupon_id = coupon["id"]

            if not best_coupon_id:
                for coupon in brand_coupons:
                    if coupon["category_or_brand"] == brand:
                        discount = calculate_discount(coupon, line_total)
                        if discount > best_discount:
                            best_discount = discount
                            best_coupon_id = coupon["id"]

            if best_coupon_id and best_discount > 0:
                for coupon in category_coupons + brand_coupons:
                    if coupon["id"] == best_coupon_id and coupon["type"] == "category":
                        categories_with_discount.add(category)
                        break
                applied_coupon_ids.add(best_coupon_id)
                item_discount_total += best_discount

            order_items_data.append(
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "product_price": unit_price,
                    "quantity": quantity,
                    "applied_coupon_id": best_coupon_id,
                    "discount_amount": best_discount,
                    "line_total": line_total - best_discount,
                }
            )

        # 5. Calculate frontstore discount
        subtotal_after_items = subtotal - item_discount_total
        frontstore_discount_amount = Decimal("0")
        frontstore_coupon_id = None

        if frontstore_coupons:
            frontstore_coupons.sort(key=lambda x: x["discount_value"], reverse=True)
            for coupon in frontstore_coupons:
                if subtotal_after_items >= coupon["min_purchase_amount"]:
                    discount = calculate_discount(coupon, subtotal_after_items)
                    if discount > 0:
                        frontstore_discount_amount = discount
                        frontstore_coupon_id = coupon["id"]
                        applied_coupon_ids.add(frontstore_coupon_id)
                        break

        # 6. Calculate final totals
        discount_total = item_discount_total + frontstore_discount_amount
        final_total = subtotal - discount_total
        if final_total < 0:
            final_total = Decimal("0")

        # 7. Create order
        order_id = str(uuid.uuid4())
        self.db.execute(
            text("""
                INSERT INTO orders (id, user_id, store_id, subtotal, discount_total,
                                 final_total, status, item_count, shopping_session_id, created_at, is_simulated)
                VALUES (:id, :user_id, :store_id, :subtotal, :discount_total,
                        :final_total, 'completed', :item_count, :shopping_session_id, :created_at, true)
            """),
            {
                "id": order_id,
                "user_id": user_id,
                "store_id": store_id,
                "subtotal": float(subtotal),
                "discount_total": float(discount_total),
                "final_total": float(final_total),
                "item_count": len(cart_items),
                "shopping_session_id": session_id,
                "created_at": simulated_timestamp,
            },
        )

        # 8. Create order items with coupon data
        for item_data in order_items_data:
            self.db.execute(
                text("""
                    INSERT INTO order_items (id, order_id, product_id, product_name,
                                           product_price, quantity, applied_coupon_id,
                                           discount_amount, line_total)
                    VALUES (:id, :order_id, :product_id, :product_name,
                            :product_price, :quantity, :applied_coupon_id,
                            :discount_amount, :line_total)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "product_id": item_data["product_id"],
                    "product_name": item_data["product_name"],
                    "product_price": float(item_data["product_price"]),
                    "quantity": item_data["quantity"],
                    "applied_coupon_id": item_data["applied_coupon_id"],
                    "discount_amount": float(item_data["discount_amount"]),
                    "line_total": float(item_data["line_total"]),
                },
            )

        # 9. Track coupon redemptions
        for coupon_id in applied_coupon_ids:
            self.db.execute(
                text("""
                    INSERT INTO coupon_interactions (user_id, coupon_id, action, order_id)
                    VALUES (:user_id, :coupon_id, 'redeemed', :order_id)
                """),
                {"user_id": user_id, "coupon_id": coupon_id, "order_id": order_id},
            )

        # 10. Clear cart
        self.db.execute(
            text("DELETE FROM cart_items WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        self.db.execute(
            text("DELETE FROM cart_coupons WHERE user_id = :user_id"),
            {"user_id": user_id},
        )

        # 11. Update session status
        self.db.execute(
            text("""
                UPDATE shopping_sessions
                SET status = 'completed', ended_at = :ended_at
                WHERE id = :id
            """),
            {"id": session_id, "ended_at": simulated_timestamp},
        )

        # 12. Record event
        self._record_event(
            session_id=session_id,
            user_id=user_id,
            event_type="checkout_complete",
            payload={
                "order_id": order_id,
                "subtotal": float(subtotal),
                "discount": float(discount_total),
                "total": float(final_total),
                "item_count": len(cart_items),
                "coupons_used": len(applied_coupon_ids),
            },
            timestamp=simulated_timestamp,
        )

        logger.debug(
            f"Session {session_id[:8]}...: Checkout complete, order {order_id[:8]}..."
        )
        return order_id

    def abandon_session(
        self,
        session_id: str,
        user_id: str,
        cart_items: List[Dict[str, Any]],
        cart_total: float,
        simulated_timestamp: datetime,
    ) -> None:
        """
        Abandon shopping session (cart abandonment).

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            cart_items: List of cart items at abandonment
            cart_total: Cart value at abandonment
            simulated_timestamp: Simulated datetime
        """
        # Update session status
        self.db.execute(
            text("""
            UPDATE shopping_sessions
            SET status = 'abandoned', ended_at = :ended_at
            WHERE id = :id
        """),
            {"id": session_id, "ended_at": simulated_timestamp},
        )

        # Clear cart for abandoned sessions
        self.db.execute(
            text("DELETE FROM cart_items WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        self.db.execute(
            text("DELETE FROM cart_coupons WHERE user_id = :user_id"),
            {"user_id": user_id},
        )

        # Record cart_abandon event
        self._record_event(
            session_id=session_id,
            user_id=user_id,
            event_type="cart_abandon",
            payload={
                "cart_total": cart_total,
                "item_count": len(cart_items),
                "items": [
                    {"product_id": i["product_id"], "quantity": i.get("quantity", 1)}
                    for i in cart_items
                ],
            },
            timestamp=simulated_timestamp,
        )

        logger.debug(
            f"Session {session_id[:8]}...: Abandoned (${cart_total:.2f}, {len(cart_items)} items)"
        )

    def _record_event(
        self,
        session_id: str,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        timestamp: datetime,
    ) -> None:
        """
        Record a shopping session event.

        Args:
            session_id: Shopping session UUID
            user_id: User UUID
            event_type: Event type string
            payload: Event data as dictionary
            timestamp: Event timestamp
        """
        self.db.execute(
            text("""
            INSERT INTO shopping_session_events
            (id, session_id, user_id, event_type, payload, created_at)
            VALUES
            (:id, :session_id, :user_id, :event_type, :payload, :created_at)
        """),
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "event_type": event_type,
                "payload": json.dumps(payload),
                "created_at": timestamp,
            },
        )


# Module-level singleton for use in graph nodes
_actions_instance: Optional[ShoppingActions] = None


def set_actions(db: Session) -> ShoppingActions:
    """
    Set the global ShoppingActions instance.

    Args:
        db: SQLAlchemy Session

    Returns:
        ShoppingActions instance
    """
    global _actions_instance
    _actions_instance = ShoppingActions(db)
    return _actions_instance


def get_actions() -> ShoppingActions:
    """
    Get the global ShoppingActions instance.

    Raises:
        RuntimeError: If actions not initialized via set_actions()

    Returns:
        ShoppingActions instance
    """
    if _actions_instance is None:
        raise RuntimeError(
            "ShoppingActions not initialized. Call set_actions(db) first."
        )
    return _actions_instance
