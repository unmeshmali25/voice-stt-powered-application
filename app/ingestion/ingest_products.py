#!/usr/bin/env python3
"""
Ingest products from JSON file into PostgreSQL database.
Loads sample product data with images, prices, ratings, and categories.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:dev@localhost:5432/voiceoffers")

# Fix DATABASE_URL if it contains special characters in password
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Parse and encode DATABASE_URL to handle special characters
if DATABASE_URL and "://" in DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    if parsed.username and parsed.password:
        # URL-encode username and password to handle special characters
        encoded_username = quote_plus(parsed.username)
        encoded_password = quote_plus(parsed.password)
        
        # Reconstruct the URL with encoded credentials
        netloc = f"{encoded_username}:{encoded_password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        
        DATABASE_URL = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"


def load_products_data() -> Dict[str, Any]:
    """Load products data from JSON file"""
    if not PRODUCTS_FILE.exists():
        raise FileNotFoundError(f"Products file not found: {PRODUCTS_FILE}")
    
    with open(PRODUCTS_FILE, 'r') as f:
        data = json.load(f)
    
    if "products" not in data:
        raise ValueError("JSON file must contain 'products' key")
    
    return data


def clear_products(session):
    """Clear all existing products from the database"""
    print("Clearing existing products...")
    result = session.execute(text("DELETE FROM products"))
    deleted = result.rowcount
    session.commit()
    print(f"✓ Deleted {deleted} existing products")


def insert_products(session, products: List[Dict[str, Any]]):
    """Insert products into the database"""
    print(f"Inserting {len(products)} products...")
    
    inserted = 0
    for product in products:
        try:
            session.execute(
                text("""
                    INSERT INTO products 
                    (name, description, image_url, price, rating, review_count, 
                     category, brand, promo_text, in_stock)
                    VALUES 
                    (:name, :description, :image_url, :price, :rating, :review_count, 
                     :category, :brand, :promo_text, :in_stock)
                """),
                {
                    "name": product['name'],
                    "description": product.get('description'),
                    "image_url": product['image_url'],
                    "price": product['price'],
                    "rating": product.get('rating'),
                    "review_count": product.get('review_count', 0),
                    "category": product.get('category'),
                    "brand": product.get('brand'),
                    "promo_text": product.get('promo_text'),
                    "in_stock": product.get('in_stock', True)
                }
            )
            inserted += 1
        except Exception as e:
            print(f"✗ Failed to insert product '{product.get('name', 'Unknown')}': {e}")
            continue
    
    session.commit()
    print(f"✓ Successfully inserted {inserted} products")


def verify_products(session):
    """Verify products were inserted correctly"""
    result = session.execute(text("SELECT COUNT(*) FROM products"))
    count = result.scalar()
    print(f"✓ Total products in database: {count}")
    
    # Show sample products
    result = session.execute(
        text("SELECT name, category, price, rating FROM products LIMIT 5")
    )
    print("\nSample products:")
    for row in result:
        print(f"  - {row[0]} (${row[2]:.2f}) - {row[1]} - Rating: {row[3] or 'N/A'}")


def main():
    """Main ingestion process"""
    print("=" * 60)
    print("Product Data Ingestion")
    print("=" * 60)
    
    # Load data
    print(f"\nLoading products from: {PRODUCTS_FILE}")
    data = load_products_data()
    products = data['products']
    print(f"✓ Loaded {len(products)} products from JSON")
    
    # Connect to database
    print(f"\nConnecting to database: {DATABASE_URL.split('@')[-1]}")
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Check if products table exists
        result = session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'products'
                )
            """)
        )
        table_exists = result.scalar()
        
        if not table_exists:
            print("\n✗ Error: 'products' table does not exist!")
            print("Please run the database schema migration first:")
            print("  psql $DATABASE_URL -f migrations/postgres_schema.sql")
            return 1
        
        print("✓ Connected to database")
        
        # Clear and insert products
        clear_products(session)
        insert_products(session, products)
        
        # Verify
        print("\nVerifying insertion:")
        verify_products(session)
        
        print("\n" + "=" * 60)
        print("✓ Product ingestion completed successfully!")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error during ingestion: {e}")
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())

