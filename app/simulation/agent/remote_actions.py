"""
Remote Shopping Actions - HTTP API Implementation

This module provides an implementation of ShoppingActions that performs
cart and checkout operations via HTTP API calls to the backend.
This validates the server's handling of real traffic and enforces
business logic via the actual API endpoints.
"""

import logging
import json
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.simulation.agent.actions import ShoppingActions

logger = logging.getLogger(__name__)

class RemoteShoppingActions(ShoppingActions):
    """
    Executes shopping actions via HTTP API calls to a remote or local server.
    Inherits from ShoppingActions to maintain interface compatibility.
    """

    def __init__(self, db: Session, api_base_url: str = "http://localhost:8000"):
        """
        Initialize with DB session and API base URL.
        
        Args:
            db: SQLAlchemy Session (still needed for read-only / metadata ops)
            api_base_url: Base URL for API calls (e.g., https://voiceoffers-production.up.railway.app)
        """
        super().__init__(db)
        self.api_base_url = api_base_url.rstrip("/")
        self.client = httpx.Client(timeout=10.0)

    def _get_headers(self, user_id: str, agent_id: str = "unknown") -> Dict[str, str]:
        """Generate auth headers for API calls."""
        # In simulation mode, we use the "Bearer dev:<agent_id>" format
        # which is accepted by verify_token in main.py when SIMULATION_MODE=true
        return {
            "Authorization": f"Bearer dev:{agent_id}",
            "Content-Type": "application/json"
        }

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
        Add item to cart via API.
        POST /api/cart/items
        """
        # Determine agent_id from user_id if possible, or pass generic.
        # Ideally, we should pass the agent_id to this method, but for now 
        # we might rely on the user_id mapping.
        # Note: The API verify_token expects "Bearer dev:<agent_id>" to map to a user_id.
        # If we only have user_id, we might need a reverse lookup or just assume 
        # the orchestrator passes the agent_id in a context.
        # For now, let's look up the agent_id from the DB using the user_id.
        
        agent_id = self._lookup_agent_id(user_id)
        
        url = f"{self.api_base_url}/api/cart/items"
        payload = {
            "product_id": product_id,
            "quantity": quantity
        }
        
        try:
            response = self.client.post(
                url, 
                json=payload, 
                headers=self._get_headers(user_id, agent_id)
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"API add_to_cart failed: {response.status_code} - {response.text}")
                # Fallback to direct DB write if API fails? 
                # No, for load testing we want to know it failed.
                # But to keep simulation running, we might log and continue.
                return

            # Still record the event locally for simulation stats consistency?
            # The API records events too, but our simulation stats might rely on local DB events table.
            # The API writes to the SAME DB, so we don't need to duplicate the event recording!
            # However, the API uses the real wall-clock time for 'created_at' usually, 
            # unless we pass a simulation header?
            # The current API implementation doesn't seem to accept a timestamp override.
            # This causes a drift between "simulated time" and "event time".
            # For scaling tests, this might be acceptable.
            
            logger.debug(f"API: Added {product_name} x{quantity} to cart")

        except Exception as e:
            logger.error(f"Remote add_to_cart exception: {e}")

    def apply_coupon(
        self,
        session_id: str,
        user_id: str,
        coupon_id: str,
        discount_details: str,
        simulated_timestamp: datetime,
    ) -> None:
        """
        Apply coupon via API.
        POST /api/cart/coupons
        """
        agent_id = self._lookup_agent_id(user_id)
        url = f"{self.api_base_url}/api/cart/coupons"
        payload = {"coupon_id": coupon_id}
        
        try:
            response = self.client.post(
                url,
                json=payload,
                headers=self._get_headers(user_id, agent_id)
            )
            if response.status_code not in (200, 201):
                logger.error(f"API apply_coupon failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Remote apply_coupon exception: {e}")

    def complete_checkout(
        self,
        session_id: str,
        user_id: str,
        store_id: str,
        simulated_timestamp: datetime,
    ) -> Optional[str]:
        """
        Complete checkout via API.
        POST /api/orders
        """
        agent_id = self._lookup_agent_id(user_id)
        url = f"{self.api_base_url}/api/orders"
        
        try:
            response = self.client.post(
                url,
                json={}, # Payload not needed as per route definition, it reads from cart
                headers=self._get_headers(user_id, agent_id)
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                order_id = data.get("order", {}).get("id")
                logger.debug(f"API: Checkout complete, order {order_id}")
                return order_id
            else:
                logger.error(f"API checkout failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Remote complete_checkout exception: {e}")
            return None

    def abandon_session(
        self,
        session_id: str,
        user_id: str,
        cart_items: List[Dict[str, Any]],
        cart_total: float,
        simulated_timestamp: datetime,
    ) -> None:
        """
        Abandon session via API (Clear cart).
        DELETE /api/cart
        """
        agent_id = self._lookup_agent_id(user_id)
        url = f"{self.api_base_url}/api/cart"
        
        try:
            # We treat abandonment as clearing the cart
            self.client.delete(
                url,
                headers=self._get_headers(user_id, agent_id)
            )
            
            # We still need to mark the session as abandoned in the DB
            # because the API doesn't have an explicit "abandon session" endpoint 
            # that updates the shopping_sessions status.
            super().abandon_session(session_id, user_id, cart_items, cart_total, simulated_timestamp)
            
        except Exception as e:
            logger.error(f"Remote abandon_session exception: {e}")

    def _lookup_agent_id(self, user_id: str) -> str:
        """Helper to find agent_id for a user_id (cached)."""
        if not hasattr(self, "_agent_cache"):
            self._agent_cache = {}
            
        if user_id in self._agent_cache:
            return self._agent_cache[user_id]
            
        # Query DB
        result = self.db.execute(
            text("SELECT agent_id FROM agents WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchone()
        
        agent_id = result[0] if result else "unknown"
        self._agent_cache[user_id] = agent_id
        return agent_id
