#!/usr/bin/env python3
"""
Ingest products from JSON file into PostgreSQL database.
Loads sample product data with images, prices, ratings, and categories.

Usage:
    python app/ingestion/ingest_products.py [OPTIONS]

Options:
    --dry-run       Show what would be done without making changes
    --env ENV       Target environment (dev, staging, production)
    --help          Show this help message

Environment Variables:
    DATABASE_URL              Primary database connection string
    DEV_DATABASE_URL          Development database URL
    STAGING_DATABASE_URL      Staging database URL  
    PRODUCTION_DATABASE_URL   Production database URL
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qsl, urlencode

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Pre-parse --env flag to load correct env file before setting up DATABASE_URL
def get_env_file():
    """Determine which env file to load based on --env argument."""
    for i, arg in enumerate(sys.argv):
        if arg == "--env" and i + 1 < len(sys.argv):
            env = sys.argv[i + 1].lower()
            if env in ("staging",):
                return ".env.staging"
            elif env in ("production", "prod"):
                return ".env.production"
    return ".env"

ENV_FILE = get_env_file()
env_path = Path(__file__).parent.parent.parent / ENV_FILE
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from: {ENV_FILE}")
else:
    load_dotenv()

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"


def get_database_url(env: Optional[str] = None) -> str:
    """Get database URL for the specified environment."""
    # The correct env file is already loaded, so just use DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        if env:
            print(f"Error: DATABASE_URL not set in .env.{env}")
        else:
            print("Error: DATABASE_URL not set")
        print("Please set DATABASE_URL environment variable")
        sys.exit(1)
    
    return normalize_database_url(db_url)


def normalize_database_url(db_url: str) -> str:
    """Normalize and encode DATABASE_URL for SQLAlchemy compatibility."""
    if not db_url:
        return db_url
    
    # Fix postgres:// to postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    # Parse and encode credentials
    if "://" in db_url:
        parsed = urlparse(db_url)
        if parsed.username and parsed.password:
            # URL-encode username and password to handle special characters
            encoded_username = quote_plus(parsed.username)
            encoded_password = quote_plus(parsed.password)
            
            # Reconstruct the URL with encoded credentials
            netloc = f"{encoded_username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            
            # Parse existing query params and ensure sslmode for remote hosts
            query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if parsed.hostname not in ("localhost", "127.0.0.1"):
                query_params.setdefault("sslmode", "require")
            
            db_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                urlencode(query_params) if query_params else "",
                parsed.fragment
            ))
    
    return db_url


def detect_environment(db_url: str) -> str:
    """Detect environment from database URL."""
    if not db_url:
        return "unknown"
    
    url_lower = db_url.lower()
    if "localhost" in url_lower or "127.0.0.1" in url_lower:
        return "dev"
    elif "staging" in url_lower:
        return "staging"
    elif "prod" in url_lower:
        return "production"
    else:
        return "remote"


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


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest products from JSON file into PostgreSQL database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Ingest to local dev database
    python app/ingestion/ingest_products.py

    # Ingest to staging
    python app/ingestion/ingest_products.py --env staging

    # Dry run to see what would happen
    python app/ingestion/ingest_products.py --dry-run

    # Use explicit DATABASE_URL
    DATABASE_URL="postgresql://..." python app/ingestion/ingest_products.py
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "production", "prod"],
        help="Target environment (uses corresponding DATABASE_URL)"
    )
    return parser.parse_args()


def main():
    """Main ingestion process"""
    args = parse_args()
    dry_run = args.dry_run
    
    print("=" * 60)
    print("Product Data Ingestion")
    if dry_run:
        print("(DRY RUN - No changes will be made)")
    print("=" * 60)
    
    # Get database URL for target environment
    database_url = get_database_url(args.env)
    detected_env = detect_environment(database_url)
    
    # Load data
    print(f"\nLoading products from: {PRODUCTS_FILE}")
    data = load_products_data()
    products = data['products']
    print(f"✓ Loaded {len(products)} products from JSON")
    
    # Show target environment
    print(f"\nTarget Environment: {detected_env.upper()}")
    
    # Connect to database (hide credentials in output)
    db_display = database_url.split('@')[-1] if '@' in database_url else database_url
    print(f"Connecting to database: {db_display}")
    
    if dry_run:
        print("\n[DRY RUN] Would perform the following:")
        print(f"  1. Connect to database: {db_display}")
        print(f"  2. Delete all existing products")
        print(f"  3. Insert {len(products)} products")
        print("\nSample products that would be inserted:")
        for product in products[:5]:
            print(f"  - {product['name']} (${product['price']:.2f})")
        if len(products) > 5:
            print(f"  ... and {len(products) - 5} more")
        print("\n" + "=" * 60)
        print("✓ Dry run completed - no changes made")
        print("=" * 60)
        return 0
    
    engine = create_engine(
        database_url,
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
        print(f"✓ Product ingestion completed successfully!")
        print(f"  Environment: {detected_env.upper()}")
        print(f"  Products: {len(products)}")
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

