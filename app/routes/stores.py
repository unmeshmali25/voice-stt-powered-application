"""
Store Routes for MultiModal AI Retail App

B-1: GET /api/stores - List all stores
B-2: GET /api/stores/{store_id} - Get single store with inventory summary
B-3: PUT /api/user/store - Set user's selected store
B-4: GET /api/user/store - Get user's selected store
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

logger = logging.getLogger("multi_modal_retail.stores")

router = APIRouter(prefix="/api", tags=["stores"])


# --- Pydantic Models ---

class SetStoreRequest(BaseModel):
    store_id: str


# --- Dependencies (imported from main) ---

def get_db():
    """Dependency placeholder - will be overridden when router is included."""
    pass


def verify_token(authorization: str = None) -> Dict[str, Any]:
    """Dependency placeholder - will be overridden when router is included."""
    pass


def set_dependencies(db_dependency, token_dependency):
    """Set the actual dependencies from main module."""
    global get_db, verify_token
    get_db = db_dependency
    verify_token = token_dependency


# --- Routes ---

@router.get("/stores")
async def list_stores(
    db: Session = Depends(lambda: get_db())
) -> JSONResponse:
    """
    B-1: List all available stores.
    Returns: { "stores": [{ id, name, created_at }] }
    """
    try:
        result = db.execute(
            text("""
                SELECT id, name, created_at
                FROM stores
                ORDER BY name ASC
            """)
        )
        rows = result.fetchall()

        stores = [
            {
                "id": str(row[0]),
                "name": row[1],
                "created_at": row[2].isoformat() if row[2] else None
            }
            for row in rows
        ]

        logger.info(f"Returning {len(stores)} stores")
        return JSONResponse({"stores": stores, "count": len(stores)}, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to list stores: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list stores: {str(e)}"
        )


@router.get("/stores/{store_id}")
async def get_store(
    store_id: str,
    db: Session = Depends(lambda: get_db())
) -> JSONResponse:
    """
    B-2: Get single store with inventory summary.
    Returns: { "store": { id, name, created_at, inventory_summary: { total_products, total_quantity } } }
    """
    try:
        # Get store details
        result = db.execute(
            text("""
                SELECT id, name, created_at
                FROM stores
                WHERE id = :store_id
            """),
            {"store_id": store_id}
        )
        store_row = result.fetchone()

        if not store_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Store not found: {store_id}"
            )

        # Get inventory summary
        inventory_result = db.execute(
            text("""
                SELECT
                    COUNT(DISTINCT product_id) as total_products,
                    COALESCE(SUM(quantity), 0) as total_quantity
                FROM store_inventory
                WHERE store_id = :store_id
            """),
            {"store_id": store_id}
        )
        inventory_row = inventory_result.fetchone()

        store = {
            "id": str(store_row[0]),
            "name": store_row[1],
            "created_at": store_row[2].isoformat() if store_row[2] else None,
            "inventory_summary": {
                "total_products": inventory_row[0] if inventory_row else 0,
                "total_quantity": int(inventory_row[1]) if inventory_row else 0
            }
        }

        logger.info(f"Returning store: {store['name']}")
        return JSONResponse({"store": store}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get store {store_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get store: {str(e)}"
        )


@router.get("/user/store")
async def get_user_store(
    user: Dict[str, Any] = Depends(lambda: verify_token()),
    db: Session = Depends(lambda: get_db())
) -> JSONResponse:
    """
    B-4: Get user's selected store.
    Returns: { "store": { id, name } | null, "has_selection": bool }
    """
    user_id = user["user_id"]

    try:
        result = db.execute(
            text("""
                SELECT s.id, s.name
                FROM user_preferences up
                JOIN stores s ON up.selected_store_id = s.id
                WHERE up.user_id = :user_id
            """),
            {"user_id": user_id}
        )
        row = result.fetchone()

        if row:
            store = {"id": str(row[0]), "name": row[1]}
            logger.info(f"User {user_id} has selected store: {store['name']}")
            return JSONResponse({
                "store": store,
                "has_selection": True
            }, status_code=200)
        else:
            logger.info(f"User {user_id} has no store selected")
            return JSONResponse({
                "store": None,
                "has_selection": False
            }, status_code=200)

    except Exception as e:
        logger.exception(f"Failed to get user store for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user store: {str(e)}"
        )


@router.put("/user/store")
async def set_user_store(
    request: SetStoreRequest,
    user: Dict[str, Any] = Depends(lambda: verify_token()),
    db: Session = Depends(lambda: get_db())
) -> JSONResponse:
    """
    B-3: Set user's selected store.
    Also clears user's cart when store changes (cart is store-specific).
    Returns: { "success": true, "store": { id, name }, "cart_cleared": bool }
    """
    user_id = user["user_id"]
    store_id = request.store_id

    try:
        # Verify store exists
        store_result = db.execute(
            text("SELECT id, name FROM stores WHERE id = :store_id"),
            {"store_id": store_id}
        )
        store_row = store_result.fetchone()

        if not store_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Store not found: {store_id}"
            )

        # Check if user has existing store selection
        existing_result = db.execute(
            text("SELECT selected_store_id FROM user_preferences WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        existing_row = existing_result.fetchone()

        cart_cleared = False
        old_store_id = existing_row[0] if existing_row else None

        # If changing stores, clear the cart
        if old_store_id and str(old_store_id) != store_id:
            db.execute(
                text("DELETE FROM cart_items WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            db.execute(
                text("DELETE FROM cart_coupons WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            cart_cleared = True
            logger.info(f"Cleared cart for user {user_id} due to store change")

        # Upsert user preference
        db.execute(
            text("""
                INSERT INTO user_preferences (user_id, selected_store_id, updated_at)
                VALUES (:user_id, :store_id, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    selected_store_id = EXCLUDED.selected_store_id,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {"user_id": user_id, "store_id": store_id}
        )
        db.commit()

        store = {"id": str(store_row[0]), "name": store_row[1]}
        logger.info(f"User {user_id} selected store: {store['name']}")

        return JSONResponse({
            "success": True,
            "store": store,
            "cart_cleared": cart_cleared
        }, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to set user store for {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set user store: {str(e)}"
        )
