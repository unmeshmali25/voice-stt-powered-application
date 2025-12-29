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

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


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
            product_id: Product UUID
            product_name: Product name for event payload
            price: Product price
            quantity: Quantity to add
            simulated_timestamp: Simulated datetime
        """
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
        cart_items: List[Dict[str, Any]],
        cart_total: float,
        coupons_applied: List[str],
        simulated_timestamp: datetime,
    ) -> str:
        """
        Complete checkout - create order record (no actual payment).

        Args:
            session_id: Current shopping session ID
            user_id: User UUID
            store_id: Store UUID
            cart_items: List of cart item dicts
            cart_total: Total cart value
            coupons_applied: List of applied coupon IDs
            simulated_timestamp: Simulated datetime

        Returns:
            Order ID (UUID string)
        """
        order_id = str(uuid.uuid4())

        # Calculate discount (simplified - 10% if coupons applied)
        discount_amount = cart_total * 0.1 if coupons_applied else 0.0
        final_total = cart_total - discount_amount

        # Create order record
        self.db.execute(
            text("""
            INSERT INTO orders
            (id, user_id, store_id, status, subtotal, discount_total, final_total,
             item_count, created_at, is_simulated)
            VALUES
            (:id, :user_id, :store_id, 'completed', :subtotal, :discount_total,
              :final_total, :item_count, :created_at, true)
        """),
            {
                "id": order_id,
                "user_id": user_id,
                "store_id": store_id,
                "subtotal": cart_total,
                "discount_total": discount_amount,
                "final_total": final_total,
                "item_count": len(cart_items),
                "created_at": simulated_timestamp,
            },
        )

        # Create order items
        for item in cart_items:
            self.db.execute(
                text("""
                INSERT INTO order_items
                (id, order_id, product_id, product_name, product_price, quantity, line_total)
                VALUES
                (:id, :order_id, :product_id, :product_name, :product_price, :quantity, :line_total)
            """),
                {
                    "id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "product_id": item["product_id"],
                    "product_name": item.get("product_name", "Unknown Product"),
                    "product_price": item.get("price", 0.0),
                    "quantity": item.get("quantity", 1),
                    "line_total": item.get("price", 0.0) * item.get("quantity", 1),
                },
            )

        # Update session status
        self.db.execute(
            text("""
            UPDATE shopping_sessions
            SET status = 'completed', ended_at = :ended_at
            WHERE id = :id
        """),
            {"id": session_id, "ended_at": simulated_timestamp},
        )

        # Record checkout_complete event
        self._record_event(
            session_id=session_id,
            user_id=user_id,
            event_type="checkout_complete",
            payload={
                "order_id": order_id,
                "subtotal": cart_total,
                "discount": discount_amount,
                "total": final_total,
                "item_count": len(cart_items),
                "coupons_used": len(coupons_applied),
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
