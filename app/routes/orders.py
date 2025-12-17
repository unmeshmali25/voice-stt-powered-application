"""
Order Routes for MultiModal AI Retail App

B-18: POST /api/orders - Create order (checkout)
B-19: GET /api/orders - Get user's order history
B-20: GET /api/orders/{order_id} - Get order details with items and applied coupons
"""

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("multi_modal_retail.orders")

router = APIRouter(prefix="/api", tags=["orders"])


# --- Dependencies (imported from main) ---

def get_db():
    """Dependency placeholder."""
    pass


def verify_token(authorization: str = None) -> Dict[str, Any]:
    """Dependency placeholder."""
    pass


def set_dependencies(db_dependency, token_dependency):
    """Set the actual dependencies from main module."""
    global get_db, verify_token
    get_db = db_dependency
    verify_token = token_dependency


# --- Helper Functions ---

def get_user_store_id(db: Session, user_id: str) -> Optional[str]:
    """Get user's selected store ID."""
    result = db.execute(
        text("SELECT selected_store_id FROM user_preferences WHERE user_id = :user_id"),
        {"user_id": user_id}
    )
    row = result.fetchone()
    return str(row[0]) if row and row[0] else None


def calculate_discount(coupon: Dict, amount: Decimal) -> Decimal:
    """Calculate discount amount based on coupon type."""
    discount_type = coupon.get("discount_type")
    discount_value = coupon.get("discount_value", Decimal('0'))
    max_discount = coupon.get("max_discount")

    if discount_type == "percent":
        discount = amount * (discount_value / Decimal('100'))
        if max_discount:
            discount = min(discount, max_discount)
        return discount
    elif discount_type == "fixed":
        return min(discount_value, amount)
    elif discount_type == "bogo":
        half_amount = amount / 2
        discount = half_amount * (discount_value / Decimal('100'))
        return discount
    return Decimal('0')


# --- Routes ---

@router.post("/orders")
async def create_order(
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    B-18: Create order (checkout).
    - Validates inventory
    - Decrements stock
    - Applies coupons with stacking rules
    - Creates order record
    - Clears cart
    - Records coupon interactions (redeemed)

    Returns: { "success": true, "order": { id, items, totals, ... } }
    """
    user_id = user["user_id"]

    try:
        # Get user's selected store
        store_id = get_user_store_id(db, user_id)
        if not store_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select a store before checkout"
            )

        # Get cart items
        items_result = db.execute(
            text("""
                SELECT
                    ci.id as cart_item_id,
                    ci.quantity,
                    ci.product_id,
                    p.name,
                    p.price,
                    p.category,
                    p.brand,
                    si.quantity as available_quantity
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                LEFT JOIN store_inventory si ON si.product_id = p.id AND si.store_id = ci.store_id
                WHERE ci.user_id = :user_id AND ci.store_id = :store_id
            """),
            {"user_id": user_id, "store_id": store_id}
        )
        cart_items = items_result.fetchall()

        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty"
            )

        # Validate inventory for all items
        for item in cart_items:
            if item[7] is None or item[1] > item[7]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient inventory for {item[3]}"
                )

        # Get selected coupons
        coupons_result = db.execute(
            text("""
                SELECT
                    c.id,
                    c.type,
                    c.discount_details,
                    c.category_or_brand,
                    c.discount_type,
                    c.discount_value,
                    c.min_purchase_amount,
                    c.max_discount
                FROM cart_coupons cc
                JOIN coupons c ON cc.coupon_id = c.id
                WHERE cc.user_id = :user_id
            """),
            {"user_id": user_id}
        )
        coupons = coupons_result.fetchall()

        # Separate coupons by type
        frontstore_coupons = []
        category_coupons = []
        brand_coupons = []

        for c in coupons:
            coupon_data = {
                "id": str(c[0]),
                "type": c[1],
                "discount_details": c[2],
                "category_or_brand": (c[3] or '').lower(),
                "discount_type": c[4],
                "discount_value": Decimal(str(c[5])) if c[5] else Decimal('0'),
                "min_purchase_amount": Decimal(str(c[6])) if c[6] else Decimal('0'),
                "max_discount": Decimal(str(c[7])) if c[7] else None
            }
            if c[1] == 'frontstore':
                frontstore_coupons.append(coupon_data)
            elif c[1] == 'category':
                category_coupons.append(coupon_data)
            elif c[1] == 'brand':
                brand_coupons.append(coupon_data)

        # Calculate totals and prepare order items
        subtotal = Decimal('0')
        order_items_data = []
        item_discount_total = Decimal('0')
        categories_with_discount = set()
        applied_coupon_ids = set()

        for item in cart_items:
            quantity = item[1]
            product_id = str(item[2])
            product_name = item[3]
            unit_price = Decimal(str(item[4])) if item[4] else Decimal('0')
            category = (item[5] or '').lower()
            brand = (item[6] or '').lower()
            line_total = unit_price * quantity
            subtotal += line_total

            # Find best applicable coupon
            best_discount = Decimal('0')
            best_coupon_id = None

            for coupon in category_coupons:
                if coupon["category_or_brand"] == category and category not in categories_with_discount:
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

            order_items_data.append({
                "product_id": product_id,
                "product_name": product_name,
                "product_price": unit_price,
                "quantity": quantity,
                "applied_coupon_id": best_coupon_id,
                "discount_amount": best_discount,
                "line_total": line_total - best_discount
            })

        # Calculate frontstore discount
        subtotal_after_items = subtotal - item_discount_total
        frontstore_discount_amount = Decimal('0')
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

        # Calculate final totals
        discount_total = item_discount_total + frontstore_discount_amount
        final_total = subtotal - discount_total
        if final_total < 0:
            final_total = Decimal('0')

        # Create order
        order_result = db.execute(
            text("""
                INSERT INTO orders (user_id, store_id, subtotal, discount_total, final_total, status)
                VALUES (:user_id, :store_id, :subtotal, :discount_total, :final_total, 'completed')
                RETURNING id, created_at
            """),
            {
                "user_id": user_id,
                "store_id": store_id,
                "subtotal": float(subtotal),
                "discount_total": float(discount_total),
                "final_total": float(final_total)
            }
        )
        order_row = order_result.fetchone()
        order_id = str(order_row[0])
        order_created_at = order_row[1]

        # Create order items
        for item_data in order_items_data:
            db.execute(
                text("""
                    INSERT INTO order_items (order_id, product_id, product_name, product_price, quantity, applied_coupon_id, discount_amount, line_total)
                    VALUES (:order_id, :product_id, :product_name, :product_price, :quantity, :applied_coupon_id, :discount_amount, :line_total)
                """),
                {
                    "order_id": order_id,
                    "product_id": item_data["product_id"],
                    "product_name": item_data["product_name"],
                    "product_price": float(item_data["product_price"]),
                    "quantity": item_data["quantity"],
                    "applied_coupon_id": item_data["applied_coupon_id"],
                    "discount_amount": float(item_data["discount_amount"]),
                    "line_total": float(item_data["line_total"])
                }
            )

        # Decrement inventory
        for item in cart_items:
            db.execute(
                text("""
                    UPDATE store_inventory
                    SET quantity = quantity - :quantity, updated_at = CURRENT_TIMESTAMP
                    WHERE store_id = :store_id AND product_id = :product_id
                """),
                {
                    "quantity": item[1],
                    "store_id": store_id,
                    "product_id": item[2]
                }
            )

        # Track coupon redemptions
        for coupon_id in applied_coupon_ids:
            db.execute(
                text("""
                    INSERT INTO coupon_interactions (user_id, coupon_id, action, order_id)
                    VALUES (:user_id, :coupon_id, 'redeemed', :order_id)
                """),
                {"user_id": user_id, "coupon_id": coupon_id, "order_id": order_id}
            )

        # Clear cart
        db.execute(
            text("DELETE FROM cart_items WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        db.execute(
            text("DELETE FROM cart_coupons WHERE user_id = :user_id"),
            {"user_id": user_id}
        )

        db.commit()

        # Get store name for response
        store_result = db.execute(
            text("SELECT name FROM stores WHERE id = :store_id"),
            {"store_id": store_id}
        )
        store_name = store_result.fetchone()[0]

        # Build response
        order_items_response = []
        for item_data in order_items_data:
            order_items_response.append({
                "product_name": item_data["product_name"],
                "quantity": item_data["quantity"],
                "unit_price": float(item_data["product_price"]),
                "discount_amount": float(item_data["discount_amount"]),
                "line_total": float(item_data["line_total"])
            })

        logger.info(f"User {user_id} completed order {order_id}: ${final_total:.2f}")

        return JSONResponse({
            "success": True,
            "order": {
                "id": order_id,
                "store": {"id": store_id, "name": store_name},
                "items": order_items_response,
                "subtotal": float(subtotal),
                "item_discounts": float(item_discount_total),
                "frontstore_discount": float(frontstore_discount_amount),
                "discount_total": float(discount_total),
                "final_total": float(final_total),
                "coupons_used": len(applied_coupon_ids),
                "created_at": order_created_at.isoformat() if order_created_at else None
            },
            "message": "Thank you for your purchase! Your order has been placed successfully."
        }, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create order for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("/orders")
async def get_orders(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    B-19: Get user's order history.
    Returns: { "orders": [...], "total": int }
    """
    user_id = user["user_id"]

    try:
        # Get total count
        count_result = db.execute(
            text("SELECT COUNT(*) FROM orders WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        total = count_result.scalar() or 0

        # Get orders with store info
        result = db.execute(
            text("""
                SELECT
                    o.id,
                    o.store_id,
                    s.name as store_name,
                    o.subtotal,
                    o.discount_total,
                    o.final_total,
                    o.status,
                    o.created_at,
                    (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
                FROM orders o
                JOIN stores s ON o.store_id = s.id
                WHERE o.user_id = :user_id
                ORDER BY o.created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"user_id": user_id, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()

        orders = []
        for row in rows:
            orders.append({
                "id": str(row[0]),
                "store": {"id": str(row[1]), "name": row[2]},
                "subtotal": float(row[3]) if row[3] else 0,
                "discount_total": float(row[4]) if row[4] else 0,
                "final_total": float(row[5]) if row[5] else 0,
                "status": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
                "item_count": row[8] or 0
            })

        logger.info(f"User {user_id} fetched {len(orders)} orders")
        return JSONResponse({
            "orders": orders,
            "total": total
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to get orders for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders: {str(e)}"
        )


@router.get("/orders/{order_id}")
async def get_order_detail(
    order_id: str,
    user: Dict[str, Any] = Depends(verify_token),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    B-20: Get order details with items and applied coupons (receipt view).
    Returns: { "order": { id, store, items, coupons, totals, ... } }
    """
    user_id = user["user_id"]

    try:
        # Get order
        order_result = db.execute(
            text("""
                SELECT
                    o.id,
                    o.store_id,
                    s.name as store_name,
                    o.subtotal,
                    o.discount_total,
                    o.final_total,
                    o.status,
                    o.created_at
                FROM orders o
                JOIN stores s ON o.store_id = s.id
                WHERE o.id = :order_id AND o.user_id = :user_id
            """),
            {"order_id": order_id, "user_id": user_id}
        )
        order_row = order_result.fetchone()

        if not order_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        # Get order items with coupon details
        items_result = db.execute(
            text("""
                SELECT
                    oi.id,
                    oi.product_id,
                    oi.product_name,
                    oi.product_price,
                    oi.quantity,
                    oi.applied_coupon_id,
                    oi.discount_amount,
                    oi.line_total,
                    c.discount_details as coupon_details,
                    c.type as coupon_type
                FROM order_items oi
                LEFT JOIN coupons c ON oi.applied_coupon_id = c.id
                WHERE oi.order_id = :order_id
                ORDER BY oi.created_at
            """),
            {"order_id": order_id}
        )
        item_rows = items_result.fetchall()

        items = []
        applied_coupons = {}

        for row in item_rows:
            items.append({
                "id": str(row[0]),
                "product_id": str(row[1]),
                "product_name": row[2],
                "unit_price": float(row[3]) if row[3] else 0,
                "quantity": row[4],
                "discount_amount": float(row[6]) if row[6] else 0,
                "line_total": float(row[7]) if row[7] else 0,
                "applied_coupon": {
                    "id": str(row[5]),
                    "details": row[8],
                    "type": row[9]
                } if row[5] else None
            })

            # Collect unique coupons
            if row[5] and str(row[5]) not in applied_coupons:
                applied_coupons[str(row[5])] = {
                    "id": str(row[5]),
                    "details": row[8],
                    "type": row[9]
                }

        # Get frontstore coupon if used (from coupon_interactions)
        frontstore_result = db.execute(
            text("""
                SELECT c.id, c.discount_details
                FROM coupon_interactions ci
                JOIN coupons c ON ci.coupon_id = c.id
                WHERE ci.order_id = :order_id
                  AND ci.action = 'redeemed'
                  AND c.type = 'frontstore'
            """),
            {"order_id": order_id}
        )
        frontstore_rows = frontstore_result.fetchall()

        frontstore_coupons = []
        for row in frontstore_rows:
            frontstore_coupons.append({
                "id": str(row[0]),
                "details": row[1],
                "type": "frontstore"
            })

        # Calculate item-level discount total
        item_discount_total = sum(item.get("discount_amount", 0) for item in items)
        frontstore_discount = float(order_row[4]) - item_discount_total if order_row[4] else 0
        if frontstore_discount < 0:
            frontstore_discount = 0

        order = {
            "id": str(order_row[0]),
            "store": {"id": str(order_row[1]), "name": order_row[2]},
            "items": items,
            "applied_coupons": {
                "item_level": list(applied_coupons.values()),
                "frontstore": frontstore_coupons
            },
            "totals": {
                "subtotal": float(order_row[3]) if order_row[3] else 0,
                "item_discounts": item_discount_total,
                "frontstore_discount": frontstore_discount,
                "discount_total": float(order_row[4]) if order_row[4] else 0,
                "final_total": float(order_row[5]) if order_row[5] else 0
            },
            "status": order_row[6],
            "created_at": order_row[7].isoformat() if order_row[7] else None
        }

        logger.info(f"User {user_id} fetched order details for {order_id}")
        return JSONResponse({"order": order}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get order detail for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order detail: {str(e)}"
        )
