"""
Cart Routes for MultiModal AI Retail App

B-8: GET /api/cart - Get user's cart items with product details
B-9: POST /api/cart/items - Add item to cart
B-10: PUT /api/cart/items/{item_id} - Update cart item quantity
B-11: DELETE /api/cart/items/{item_id} - Remove item from cart
B-12: DELETE /api/cart - Clear entire cart
B-14: GET /api/coupons/eligible - Get coupons eligible for current cart
B-15: POST /api/cart/coupons - Add coupon to cart
B-16: DELETE /api/cart/coupons/{coupon_id} - Remove coupon from cart
B-17: GET /api/cart/summary - Calculate cart totals with coupon stacking logic
B-21: POST /api/coupon-interactions - Track coupon interaction
B-22: Coupon stacking logic (integrated)
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

logger = logging.getLogger("multi_modal_retail.cart")

router = APIRouter(prefix="/api", tags=["cart"])

from app.session_tracking import (
    get_selected_store_id as _get_selected_store_id_for_session,
    get_shopping_session_id,
    touch_shopping_session,
    record_shopping_event,
)

# --- Pydantic Models ---

class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1


class UpdateCartItemRequest(BaseModel):
    quantity: int


class AddCouponRequest(BaseModel):
    coupon_id: str


class CouponInteractionRequest(BaseModel):
    coupon_id: str
    action: str  # 'added_to_cart', 'removed_from_cart', 'applied', 'redeemed'
    order_id: Optional[str] = None


# --- Dependencies (imported from main) ---

_db_dependency = None
_token_dependency = None


def set_dependencies(db_dependency, token_dependency):
    """Set the actual dependencies from main module."""
    global _db_dependency, _token_dependency
    _db_dependency = db_dependency
    _token_dependency = token_dependency


def db_dep():
    """DB dependency wrapper that defers to the injected dependency at runtime."""
    if _db_dependency is None:
        raise RuntimeError("DB dependency not configured. Did you call set_dependencies()?")
    yield from _db_dependency()


def token_dep(authorization: str = Header(None)) -> Dict[str, Any]:
    """Auth dependency wrapper that defers to the injected dependency at runtime."""
    if _token_dependency is None:
        raise RuntimeError("Token dependency not configured. Did you call set_dependencies()?")
    return _token_dependency(authorization)


# --- Helper Functions ---

def get_user_store_id(db: Session, user_id: str) -> Optional[str]:
    """Get user's selected store ID."""
    result = db.execute(
        text("SELECT selected_store_id FROM user_preferences WHERE user_id = :user_id"),
        {"user_id": user_id}
    )
    row = result.fetchone()
    return str(row[0]) if row and row[0] else None


def check_inventory(db: Session, store_id: str, product_id: str, quantity: int) -> bool:
    """Check if store has enough inventory for the requested quantity."""
    result = db.execute(
        text("""
            SELECT quantity FROM store_inventory
            WHERE store_id = :store_id AND product_id = :product_id
        """),
        {"store_id": store_id, "product_id": product_id}
    )
    row = result.fetchone()
    return row and row[0] >= quantity


# --- Routes ---

@router.get("/cart")
async def get_cart(
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-8: Get user's cart items with product details and selected coupons.
    Returns: { "items": [...], "coupons": [...], "store": {...}, "item_count": int }
    """
    user_id = user["user_id"]

    try:
        # Get user's selected store
        store_id = get_user_store_id(db, user_id)

        if not store_id:
            return JSONResponse({
                "items": [],
                "coupons": [],
                "store": None,
                "item_count": 0,
                "message": "no_store_selected"
            }, status_code=200)

        # Get store info
        store_result = db.execute(
            text("SELECT id, name FROM stores WHERE id = :store_id"),
            {"store_id": store_id}
        )
        store_row = store_result.fetchone()
        store = {"id": str(store_row[0]), "name": store_row[1]} if store_row else None

        # Get cart items with product details and inventory
        result = db.execute(
            text("""
                SELECT
                    ci.id as cart_item_id,
                    ci.quantity,
                    ci.created_at,
                    p.id as product_id,
                    p.name,
                    p.description,
                    p.image_url,
                    p.price,
                    p.rating,
                    p.review_count,
                    p.category,
                    p.brand,
                    p.promo_text,
                    si.quantity as available_quantity
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                LEFT JOIN store_inventory si ON si.product_id = p.id AND si.store_id = ci.store_id
                WHERE ci.user_id = :user_id AND ci.store_id = :store_id
                ORDER BY ci.created_at DESC
            """),
            {"user_id": user_id, "store_id": store_id}
        )
        rows = result.fetchall()

        items = []
        for row in rows:
            items.append({
                "cart_item_id": str(row[0]),
                "quantity": row[1],
                "added_at": row[2].isoformat() if row[2] else None,
                "product": {
                    "id": str(row[3]),
                    "name": row[4],
                    "description": row[5],
                    "image_url": row[6],
                    "price": float(row[7]) if row[7] else 0.0,
                    "rating": float(row[8]) if row[8] else None,
                    "review_count": row[9] or 0,
                    "category": row[10],
                    "brand": row[11],
                    "promo_text": row[12]
                },
                "available_quantity": row[13] or 0,
                "line_total": float(row[7] * row[1]) if row[7] else 0.0
            })

        # Get selected coupons
        coupon_result = db.execute(
            text("""
                SELECT
                    c.id,
                    c.type,
                    c.discount_details,
                    c.category_or_brand,
                    c.expiration_date,
                    c.terms,
                    c.discount_type,
                    c.discount_value,
                    c.min_purchase_amount,
                    c.max_discount
                FROM cart_coupons cc
                JOIN coupons c ON cc.coupon_id = c.id
                WHERE cc.user_id = :user_id
                ORDER BY c.type, c.created_at
            """),
            {"user_id": user_id}
        )
        coupon_rows = coupon_result.fetchall()

        coupons = [
            {
                "id": str(row[0]),
                "type": row[1],
                "discount_details": row[2],
                "category_or_brand": row[3],
                "expiration_date": row[4].isoformat() if row[4] else None,
                "terms": row[5],
                "discount_type": row[6],
                "discount_value": float(row[7]) if row[7] else 0,
                "min_purchase_amount": float(row[8]) if row[8] else 0,
                "max_discount": float(row[9]) if row[9] else None
            }
            for row in coupon_rows
        ]

        item_count = sum(item["quantity"] for item in items)

        logger.info(f"User {user_id} cart: {len(items)} products, {item_count} items, {len(coupons)} coupons")
        return JSONResponse({
            "items": items,
            "coupons": coupons,
            "store": store,
            "item_count": item_count
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to get cart for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cart: {str(e)}"
        )


@router.post("/cart/items")
async def add_to_cart(
    request: AddToCartRequest,
    http_request: Request,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-9: Add item to cart.
    Returns: { "success": true, "cart_item": {...} }
    """
    user_id = user["user_id"]
    product_id = request.product_id
    quantity = request.quantity

    # Validate product_id is UUID
    try:
        UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid product ID format: {product_id}"
        )

    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be at least 1"
        )

    try:
        # Get user's selected store
        store_id = get_user_store_id(db, user_id)

        if not store_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select a store first"
            )

        # Verify product exists
        product_result = db.execute(
            text("SELECT id, name, price FROM products WHERE id = :product_id"),
            {"product_id": product_id}
        )
        product_row = product_result.fetchone()

        if not product_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product not found: {product_id}"
            )

        # Check inventory
        if not check_inventory(db, store_id, product_id, quantity):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient inventory"
            )

        # Add or update cart item
        db.execute(
            text("""
                INSERT INTO cart_items (user_id, store_id, product_id, quantity)
                VALUES (:user_id, :store_id, :product_id, :quantity)
                ON CONFLICT (user_id, store_id, product_id)
                DO UPDATE SET
                    quantity = cart_items.quantity + EXCLUDED.quantity,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "user_id": user_id,
                "store_id": store_id,
                "product_id": product_id,
                "quantity": quantity
            }
        )

        # Session event tracking (best-effort inside transaction)
        session_id = get_shopping_session_id(http_request)
        if session_id:
            touch_shopping_session(
                db,
                session_id=session_id,
                user_id=user_id,
                store_id=_get_selected_store_id_for_session(db, user_id),
            )
            record_shopping_event(
                db,
                session_id=session_id,
                user_id=user_id,
                event_type="cart_add_item",
                payload={"product_id": product_id, "quantity": quantity, "store_id": store_id},
            )

        db.commit()

        # Get updated cart item
        result = db.execute(
            text("""
                SELECT ci.id, ci.quantity, p.name, p.price
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.user_id = :user_id
                  AND ci.store_id = :store_id
                  AND ci.product_id = :product_id
            """),
            {"user_id": user_id, "store_id": store_id, "product_id": product_id}
        )
        row = result.fetchone()

        cart_item = {
            "id": str(row[0]),
            "quantity": row[1],
            "product_name": row[2],
            "unit_price": float(row[3]) if row[3] else 0,
            "line_total": float(row[3] * row[1]) if row[3] else 0
        }

        logger.info(f"User {user_id} added {quantity}x {product_row[1]} to cart")
        return JSONResponse({
            "success": True,
            "cart_item": cart_item
        }, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to add to cart for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add to cart: {str(e)}"
        )


@router.put("/cart/items/{item_id}")
async def update_cart_item(
    item_id: str,
    request: UpdateCartItemRequest,
    http_request: Request,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-10: Update cart item quantity.
    Returns: { "success": true, "cart_item": {...} }
    """
    user_id = user["user_id"]
    quantity = request.quantity

    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be at least 1"
        )

    try:
        # Get cart item
        result = db.execute(
            text("""
                SELECT ci.id, ci.store_id, ci.product_id, p.name
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.id = :item_id AND ci.user_id = :user_id
            """),
            {"item_id": item_id, "user_id": user_id}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )

        store_id = str(row[1])
        product_id = str(row[2])

        # Check inventory
        if not check_inventory(db, store_id, product_id, quantity):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient inventory for requested quantity"
            )

        # Update quantity
        db.execute(
            text("""
                UPDATE cart_items
                SET quantity = :quantity, updated_at = CURRENT_TIMESTAMP
                WHERE id = :item_id AND user_id = :user_id
            """),
            {"quantity": quantity, "item_id": item_id, "user_id": user_id}
        )

        session_id = get_shopping_session_id(http_request)
        if session_id:
            touch_shopping_session(
                db,
                session_id=session_id,
                user_id=user_id,
                store_id=_get_selected_store_id_for_session(db, user_id),
            )
            record_shopping_event(
                db,
                session_id=session_id,
                user_id=user_id,
                event_type="cart_update_qty",
                payload={"cart_item_id": item_id, "quantity": quantity},
            )

        db.commit()

        # Get updated cart item
        result = db.execute(
            text("""
                SELECT ci.id, ci.quantity, p.name, p.price
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.id = :item_id
            """),
            {"item_id": item_id}
        )
        updated_row = result.fetchone()

        cart_item = {
            "id": str(updated_row[0]),
            "quantity": updated_row[1],
            "product_name": updated_row[2],
            "unit_price": float(updated_row[3]) if updated_row[3] else 0,
            "line_total": float(updated_row[3] * updated_row[1]) if updated_row[3] else 0
        }

        logger.info(f"User {user_id} updated cart item {item_id} to quantity {quantity}")
        return JSONResponse({
            "success": True,
            "cart_item": cart_item
        }, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update cart item for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update cart item: {str(e)}"
        )


@router.delete("/cart/items/{item_id}")
async def remove_cart_item(
    item_id: str,
    http_request: Request,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-11: Remove item from cart.
    Returns: { "success": true }
    """
    user_id = user["user_id"]

    try:
        # Verify item belongs to user
        result = db.execute(
            text("SELECT id FROM cart_items WHERE id = :item_id AND user_id = :user_id"),
            {"item_id": item_id, "user_id": user_id}
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )

        db.execute(
            text("DELETE FROM cart_items WHERE id = :item_id AND user_id = :user_id"),
            {"item_id": item_id, "user_id": user_id}
        )

        session_id = get_shopping_session_id(http_request)
        if session_id:
            touch_shopping_session(
                db,
                session_id=session_id,
                user_id=user_id,
                store_id=_get_selected_store_id_for_session(db, user_id),
            )
            record_shopping_event(
                db,
                session_id=session_id,
                user_id=user_id,
                event_type="cart_remove_item",
                payload={"cart_item_id": item_id},
            )

        db.commit()

        logger.info(f"User {user_id} removed cart item {item_id}")
        return JSONResponse({"success": True}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to remove cart item for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove cart item: {str(e)}"
        )


@router.delete("/cart")
async def clear_cart(
    http_request: Request,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-12: Clear entire cart (items and coupons).
    Returns: { "success": true, "items_removed": int, "coupons_removed": int }
    """
    user_id = user["user_id"]

    try:
        # Count items before delete
        items_result = db.execute(
            text("SELECT COUNT(*) FROM cart_items WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        items_count = items_result.scalar() or 0

        coupons_result = db.execute(
            text("SELECT COUNT(*) FROM cart_coupons WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        coupons_count = coupons_result.scalar() or 0

        # Delete items and coupons
        db.execute(
            text("DELETE FROM cart_items WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        db.execute(
            text("DELETE FROM cart_coupons WHERE user_id = :user_id"),
            {"user_id": user_id}
        )

        session_id = get_shopping_session_id(http_request)
        if session_id:
            touch_shopping_session(
                db,
                session_id=session_id,
                user_id=user_id,
                store_id=_get_selected_store_id_for_session(db, user_id),
            )
            record_shopping_event(
                db,
                session_id=session_id,
                user_id=user_id,
                event_type="cart_clear",
                payload={"items_removed": int(items_count), "coupons_removed": int(coupons_count)},
            )

        db.commit()

        logger.info(f"User {user_id} cleared cart: {items_count} items, {coupons_count} coupons")
        return JSONResponse({
            "success": True,
            "items_removed": items_count,
            "coupons_removed": coupons_count
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to clear cart for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cart: {str(e)}"
        )


@router.get("/coupons/eligible")
async def get_eligible_coupons(
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-14: Get coupons eligible for current cart.
    Checks user's assigned coupons against cart contents.
    Returns: { "eligible": [...], "ineligible": [...] }
    """
    user_id = user["user_id"]

    try:
        # Get cart contents
        store_id = get_user_store_id(db, user_id)
        if not store_id:
            return JSONResponse({
                "eligible": [],
                "ineligible": [],
                "message": "no_store_selected"
            }, status_code=200)

        # Get cart items with categories and brands
        cart_result = db.execute(
            text("""
                SELECT
                    p.category,
                    p.brand,
                    SUM(ci.quantity * p.price) as subtotal
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.user_id = :user_id AND ci.store_id = :store_id
                GROUP BY p.category, p.brand
            """),
            {"user_id": user_id, "store_id": store_id}
        )
        cart_rows = cart_result.fetchall()

        cart_categories = set()
        cart_brands = set()
        cart_subtotal = Decimal('0')

        for row in cart_rows:
            if row[0]:
                cart_categories.add(row[0].lower())
            if row[1]:
                cart_brands.add(row[1].lower())
            cart_subtotal += Decimal(str(row[2])) if row[2] else Decimal('0')

        # Get user's coupons
        coupon_result = db.execute(
            text("""
                SELECT
                    c.id,
                    c.type,
                    c.discount_details,
                    c.category_or_brand,
                    c.expiration_date,
                    c.terms,
                    c.discount_type,
                    c.discount_value,
                    c.min_purchase_amount,
                    c.max_discount
                FROM coupons c
                JOIN user_coupons uc ON c.id = uc.coupon_id
                WHERE uc.user_id = :user_id
                  AND uc.eligible_until > NOW()
                  AND c.expiration_date > NOW()
                  AND (c.is_active IS NULL OR c.is_active = true)
                ORDER BY c.type, c.discount_value DESC NULLS LAST
            """),
            {"user_id": user_id}
        )
        coupon_rows = coupon_result.fetchall()

        # Get already selected coupons
        selected_result = db.execute(
            text("SELECT coupon_id FROM cart_coupons WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        selected_ids = {str(row[0]) for row in selected_result.fetchall()}

        eligible = []
        ineligible = []

        for row in coupon_rows:
            coupon = {
                "id": str(row[0]),
                "type": row[1],
                "discount_details": row[2],
                "category_or_brand": row[3],
                "expiration_date": row[4].isoformat() if row[4] else None,
                "terms": row[5],
                "discount_type": row[6],
                "discount_value": float(row[7]) if row[7] else 0,
                "min_purchase_amount": float(row[8]) if row[8] else 0,
                "max_discount": float(row[9]) if row[9] else None,
                "is_selected": str(row[0]) in selected_ids
            }

            is_eligible = False
            reason = None

            # Check eligibility based on type
            if row[1] == 'frontstore':
                # Frontstore: check minimum purchase amount
                min_amount = Decimal(str(row[8])) if row[8] else Decimal('0')
                if cart_subtotal >= min_amount:
                    is_eligible = True
                else:
                    reason = f"Minimum purchase ${min_amount:.2f} required"

            elif row[1] == 'category':
                # Category: check if cart contains matching category
                cat_or_brand = (row[3] or '').lower()
                if cat_or_brand in cart_categories:
                    is_eligible = True
                else:
                    reason = f"No {row[3]} products in cart"

            elif row[1] == 'brand':
                # Brand: check if cart contains matching brand
                cat_or_brand = (row[3] or '').lower()
                if cat_or_brand in cart_brands:
                    is_eligible = True
                else:
                    reason = f"No {row[3]} products in cart"

            if is_eligible:
                eligible.append(coupon)
            else:
                coupon["ineligible_reason"] = reason
                ineligible.append(coupon)

        logger.info(f"User {user_id}: {len(eligible)} eligible, {len(ineligible)} ineligible coupons")
        return JSONResponse({
            "eligible": eligible,
            "ineligible": ineligible,
            "cart_subtotal": float(cart_subtotal)
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to get eligible coupons for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get eligible coupons: {str(e)}"
        )


@router.post("/cart/coupons")
async def add_coupon_to_cart(
    request: AddCouponRequest,
    http_request: Request,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-15: Add coupon to cart (user selection).
    Returns: { "success": true, "coupon": {...} }
    """
    user_id = user["user_id"]
    coupon_id = request.coupon_id

    try:
        # Verify coupon exists and is assigned to user
        result = db.execute(
            text("""
                SELECT c.id, c.type, c.discount_details, c.category_or_brand
                FROM coupons c
                JOIN user_coupons uc ON c.id = uc.coupon_id
                WHERE c.id = :coupon_id
                  AND uc.user_id = :user_id
                  AND uc.eligible_until > NOW()
                  AND c.expiration_date > NOW()
            """),
            {"coupon_id": coupon_id, "user_id": user_id}
        )
        coupon_row = result.fetchone()

        if not coupon_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Coupon not found or not assigned to you"
            )

        # Add to cart_coupons
        db.execute(
            text("""
                INSERT INTO cart_coupons (user_id, coupon_id)
                VALUES (:user_id, :coupon_id)
                ON CONFLICT (user_id, coupon_id) DO NOTHING
            """),
            {"user_id": user_id, "coupon_id": coupon_id}
        )

        # Track interaction
        db.execute(
            text("""
                INSERT INTO coupon_interactions (user_id, coupon_id, action)
                VALUES (:user_id, :coupon_id, 'added_to_cart')
            """),
            {"user_id": user_id, "coupon_id": coupon_id}
        )

        session_id = get_shopping_session_id(http_request)
        if session_id:
            touch_shopping_session(
                db,
                session_id=session_id,
                user_id=user_id,
                store_id=_get_selected_store_id_for_session(db, user_id),
            )
            record_shopping_event(
                db,
                session_id=session_id,
                user_id=user_id,
                event_type="cart_add_coupon",
                payload={"coupon_id": coupon_id},
            )

        db.commit()

        coupon = {
            "id": str(coupon_row[0]),
            "type": coupon_row[1],
            "discount_details": coupon_row[2],
            "category_or_brand": coupon_row[3]
        }

        logger.info(f"User {user_id} added coupon {coupon_id} to cart")
        return JSONResponse({
            "success": True,
            "coupon": coupon
        }, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to add coupon to cart for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add coupon to cart: {str(e)}"
        )


@router.delete("/cart/coupons/{coupon_id}")
async def remove_coupon_from_cart(
    coupon_id: str,
    http_request: Request,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-16: Remove coupon from cart.
    Returns: { "success": true }
    """
    user_id = user["user_id"]

    try:
        # Track interaction
        db.execute(
            text("""
                INSERT INTO coupon_interactions (user_id, coupon_id, action)
                VALUES (:user_id, :coupon_id, 'removed_from_cart')
            """),
            {"user_id": user_id, "coupon_id": coupon_id}
        )

        db.execute(
            text("DELETE FROM cart_coupons WHERE user_id = :user_id AND coupon_id = :coupon_id"),
            {"user_id": user_id, "coupon_id": coupon_id}
        )

        session_id = get_shopping_session_id(http_request)
        if session_id:
            touch_shopping_session(
                db,
                session_id=session_id,
                user_id=user_id,
                store_id=_get_selected_store_id_for_session(db, user_id),
            )
            record_shopping_event(
                db,
                session_id=session_id,
                user_id=user_id,
                event_type="cart_remove_coupon",
                payload={"coupon_id": coupon_id},
            )

        db.commit()

        logger.info(f"User {user_id} removed coupon {coupon_id} from cart")
        return JSONResponse({"success": True}, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to remove coupon from cart for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove coupon from cart: {str(e)}"
        )


@router.get("/cart/summary")
async def get_cart_summary(
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-17: Calculate cart totals with coupon stacking logic (B-22).

    Coupon Stacking Rules:
    - Only ONE frontstore coupon can be applied (highest value)
    - Max ONE category/brand coupon per product
    - Category and brand coupons on same product are mutually exclusive
    - Frontstore coupon applies AFTER item-level discounts

    Returns: {
        "subtotal": float,
        "item_discounts": [...],
        "frontstore_discount": {...} | null,
        "discount_total": float,
        "final_total": float,
        "savings_percentage": float
    }
    """
    user_id = user["user_id"]

    try:
        store_id = get_user_store_id(db, user_id)
        if not store_id:
            return JSONResponse({
                "subtotal": 0,
                "item_discounts": [],
                "frontstore_discount": None,
                "discount_total": 0,
                "final_total": 0,
                "savings_percentage": 0,
                "message": "no_store_selected"
            }, status_code=200)

        # Get cart items
        items_result = db.execute(
            text("""
                SELECT
                    ci.id as cart_item_id,
                    ci.quantity,
                    p.id as product_id,
                    p.name,
                    p.price,
                    p.category,
                    p.brand
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.user_id = :user_id AND ci.store_id = :store_id
            """),
            {"user_id": user_id, "store_id": store_id}
        )
        items = items_result.fetchall()

        if not items:
            return JSONResponse({
                "subtotal": 0,
                "item_discounts": [],
                "frontstore_discount": None,
                "discount_total": 0,
                "final_total": 0,
                "savings_percentage": 0,
                "message": "cart_empty"
            }, status_code=200)

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

        # Pre-index coupons by category/brand for O(1) lookup instead of O(n) loop
        category_coupon_map = defaultdict(list)
        for coupon in category_coupons:
            key = coupon["category_or_brand"]
            if key:
                category_coupon_map[key].append(coupon)

        brand_coupon_map = defaultdict(list)
        for coupon in brand_coupons:
            key = coupon["category_or_brand"]
            if key:
                brand_coupon_map[key].append(coupon)

        # Calculate subtotal and item-level discounts
        subtotal = Decimal('0')
        item_discounts = []
        categories_with_discount = set()  # Track one coupon per category

        for item in items:
            cart_item_id = str(item[0])
            quantity = item[1]
            product_id = str(item[2])
            product_name = item[3]
            unit_price = Decimal(str(item[4])) if item[4] else Decimal('0')
            category = (item[5] or '').lower()
            brand = (item[6] or '').lower()
            line_total = unit_price * quantity
            subtotal += line_total

            # Find best applicable coupon for this item
            # Priority: category > brand (or best discount)
            best_discount = Decimal('0')
            best_coupon = None

            # Check category coupons using O(1) lookup (only if category not already used)
            if category not in categories_with_discount:
                for coupon in category_coupon_map.get(category, []):
                    discount = calculate_discount(coupon, line_total)
                    if discount > best_discount:
                        best_discount = discount
                        best_coupon = coupon

            # Check brand coupons using O(1) lookup (only if no category coupon applied)
            if not best_coupon:
                for coupon in brand_coupon_map.get(brand, []):
                    discount = calculate_discount(coupon, line_total)
                    if discount > best_discount:
                        best_discount = discount
                        best_coupon = coupon

            if best_coupon and best_discount > 0:
                if best_coupon["type"] == "category":
                    categories_with_discount.add(category)

                item_discounts.append({
                    "cart_item_id": cart_item_id,
                    "product_name": product_name,
                    "coupon_id": best_coupon["id"],
                    "coupon_details": best_coupon["discount_details"],
                    "discount_amount": float(best_discount)
                })

        # Calculate frontstore discount (apply to subtotal after item discounts)
        item_discount_total = sum(Decimal(str(d["discount_amount"])) for d in item_discounts)
        subtotal_after_items = subtotal - item_discount_total

        frontstore_discount = None
        frontstore_discount_amount = Decimal('0')

        if frontstore_coupons:
            # Sort by discount value (desc) and pick the best one that meets min purchase
            frontstore_coupons.sort(key=lambda x: x["discount_value"], reverse=True)

            for coupon in frontstore_coupons:
                if subtotal_after_items >= coupon["min_purchase_amount"]:
                    discount = calculate_discount(coupon, subtotal_after_items)
                    if discount > 0:
                        frontstore_discount_amount = discount
                        frontstore_discount = {
                            "coupon_id": coupon["id"],
                            "coupon_details": coupon["discount_details"],
                            "discount_amount": float(discount)
                        }
                        break

        # Calculate totals
        discount_total = item_discount_total + frontstore_discount_amount
        final_total = subtotal - discount_total

        # Ensure final_total is not negative
        if final_total < 0:
            final_total = Decimal('0')

        savings_percentage = (discount_total / subtotal * 100) if subtotal > 0 else Decimal('0')

        logger.info(f"User {user_id} cart summary: subtotal=${subtotal}, discounts=${discount_total}, final=${final_total}")

        return JSONResponse({
            "subtotal": float(subtotal),
            "item_discounts": item_discounts,
            "frontstore_discount": frontstore_discount,
            "discount_total": float(discount_total),
            "final_total": float(final_total),
            "savings_percentage": round(float(savings_percentage), 1)
        }, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to get cart summary for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cart summary: {str(e)}"
        )


@router.post("/coupon-interactions")
async def track_coupon_interaction(
    request: CouponInteractionRequest,
    user: Dict[str, Any] = Depends(token_dep),
    db: Session = Depends(db_dep)
) -> JSONResponse:
    """
    B-21: Track coupon interaction.
    Actions: 'added_to_cart', 'removed_from_cart', 'applied', 'redeemed'
    Returns: { "success": true }
    """
    user_id = user["user_id"]

    valid_actions = {'added_to_cart', 'removed_from_cart', 'applied', 'redeemed'}
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}"
        )

    try:
        db.execute(
            text("""
                INSERT INTO coupon_interactions (user_id, coupon_id, action, order_id)
                VALUES (:user_id, :coupon_id, :action, :order_id)
            """),
            {
                "user_id": user_id,
                "coupon_id": request.coupon_id,
                "action": request.action,
                "order_id": request.order_id
            }
        )
        db.commit()

        logger.info(f"User {user_id} interaction: {request.action} on coupon {request.coupon_id}")
        return JSONResponse({"success": True}, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to track coupon interaction for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track interaction: {str(e)}"
        )


def calculate_discount(coupon: Dict, amount: Decimal) -> Decimal:
    """
    Calculate discount amount based on coupon type.
    B-22: Coupon calculation logic.
    """
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
        # BOGO: discount_value is the percentage off the second item
        # For simplicity, apply as percent discount on half the amount
        half_amount = amount / 2
        discount = half_amount * (discount_value / Decimal('100'))
        return discount

    elif discount_type == "free_shipping":
        # Free shipping doesn't reduce item total
        return Decimal('0')

    return Decimal('0')
