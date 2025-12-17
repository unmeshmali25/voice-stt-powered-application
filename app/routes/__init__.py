"""
Route modules for MultiModal AI Retail App.
"""

from .stores import router as stores_router
from .cart import router as cart_router
from .orders import router as orders_router

__all__ = ["stores_router", "cart_router", "orders_router"]
