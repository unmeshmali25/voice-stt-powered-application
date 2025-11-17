#!/usr/bin/env python3
"""
Load products from data/products.json into PostgreSQL database.

Usage:
    python scripts/load_products.py
"""

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path to import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.supabase_client import supabase


def load_products():
    """Load products from JSON file into database."""

    # Load products.json
    products_file = Path(__file__).parent.parent / "data" / "products.json"

    if not products_file.exists():
        print(f"Error: {products_file} not found!")
        sys.exit(1)

    with open(products_file) as f:
        data = json.load(f)

    products = data.get("products", [])

    if not products:
        print("Error: No products found in JSON file!")
        sys.exit(1)

    print(f"Loading {len(products)} products into database...")

    # Insert products one by one
    success_count = 0
    error_count = 0

    for idx, product in enumerate(products, 1):
        try:
            # Generate UUID for product
            product_id = str(uuid4())

            # Prepare product data
            product_data = {
                "id": product_id,
                "name": product["name"],
                "description": product.get("description", ""),
                "image_url": product["image_url"],
                "price": product["price"],
                "rating": product.get("rating"),
                "review_count": product.get("review_count", 0),
                "category": product.get("category"),
                "brand": product.get("brand"),
                "promo_text": product.get("promo_text"),
                "in_stock": product.get("in_stock", True)
            }

            # Insert into database
            result = supabase.table("products").insert(product_data).execute()

            print(f"  [{idx}/{len(products)}] ✓ {product['name']}")
            success_count += 1

        except Exception as e:
            print(f"  [{idx}/{len(products)}] ✗ Error loading {product.get('name', 'unknown')}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Loading complete!")
    print(f"  Successful: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(products)}")
    print(f"{'='*60}")

    if error_count > 0:
        print("\n⚠️  Some products failed to load. Check errors above.")
        sys.exit(1)
    else:
        print("\n✅ All products loaded successfully!")


if __name__ == "__main__":
    load_products()
