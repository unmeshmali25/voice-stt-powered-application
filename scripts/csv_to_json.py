#!/usr/bin/env python3
"""
Convert products CSV to JSON format for database ingestion.

This script reads data/products.csv and generates data/products.json,
mapping image filenames to Supabase Storage URLs.

Usage:
    python scripts/csv_to_json.py

Options:
    --use-placeholder   Use placeholder Unsplash images instead of Supabase URLs
                        (useful for testing before uploading actual images)
"""

import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv

# Support --staging/--production flags
ENV_FILE = ".env"
if "--staging" in sys.argv:
    ENV_FILE = ".env.staging"
elif "--production" in sys.argv or "--prod" in sys.argv:
    ENV_FILE = ".env.production"

env_path = Path(__file__).parent.parent / ENV_FILE
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
CSV_FILE = DATA_DIR / "products.csv"
JSON_FILE = DATA_DIR / "products.json"
URL_MAPPING_FILE = DATA_DIR / "image_urls.json"

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
BUCKET_NAME = "product-images"

# Placeholder image for missing images
PLACEHOLDER_IMAGE = "https://images.unsplash.com/photo-1556911220-bff31c812dba?w=400&q=80"


def load_url_mapping() -> Dict[str, str]:
    """Load image URL mapping from file."""
    if URL_MAPPING_FILE.exists():
        with open(URL_MAPPING_FILE, "r") as f:
            return json.load(f)
    return {}


def get_image_url(filename: str, url_mapping: Dict[str, str], use_placeholder: bool = False) -> str:
    """
    Get the full URL for an image filename.
    
    Priority:
    1. URL from mapping file (if exists)
    2. Construct Supabase URL (if SUPABASE_URL is set)
    3. Use placeholder image
    """
    if use_placeholder:
        return PLACEHOLDER_IMAGE
    
    # Check URL mapping first
    if filename in url_mapping:
        return url_mapping[filename]
    
    # Construct Supabase URL if configured
    if SUPABASE_URL:
        return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"
    
    # Fallback to placeholder
    print(f"  Warning: No URL found for {filename}, using placeholder")
    return PLACEHOLDER_IMAGE


def parse_csv_row(row: Dict[str, str], url_mapping: Dict[str, str], use_placeholder: bool) -> Dict[str, Any]:
    """Parse a CSV row into a product dictionary."""
    # Get image URL
    image_filename = row.get("image_filename", "").strip()
    image_url = get_image_url(image_filename, url_mapping, use_placeholder)
    
    # Parse numeric fields
    price = float(row.get("price", "0").strip() or "0")
    rating = row.get("rating", "").strip()
    rating = float(rating) if rating else None
    review_count = row.get("review_count", "").strip()
    review_count = int(review_count) if review_count else 0
    
    # Parse boolean field
    in_stock_str = row.get("in_stock", "TRUE").strip().upper()
    in_stock = in_stock_str in ("TRUE", "1", "YES", "Y")
    
    # Build product dictionary
    product = {
        "name": row.get("name", "").strip(),
        "description": row.get("description", "").strip(),
        "image_url": image_url,
        "price": price,
        "rating": rating,
        "review_count": review_count,
        "category": row.get("category", "").strip() or None,
        "brand": row.get("brand", "").strip() or None,
        "in_stock": in_stock,
    }
    
    # Add promo_text only if present
    promo_text = row.get("promo_text", "").strip()
    if promo_text:
        product["promo_text"] = promo_text
    
    return product


def read_csv() -> List[Dict[str, str]]:
    """Read products from CSV file."""
    if not CSV_FILE.exists():
        print(f"Error: CSV file not found: {CSV_FILE}")
        sys.exit(1)
    
    products = []
    with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(row)
    
    return products


def write_json(products: List[Dict[str, Any]]):
    """Write products to JSON file."""
    output = {"products": products}
    
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Wrote {len(products)} products to: {JSON_FILE}")


def main():
    """Main conversion process."""
    print("=" * 60)
    print("CSV to JSON Product Converter")
    print("=" * 60)
    
    # Check for --use-placeholder flag
    use_placeholder = "--use-placeholder" in sys.argv
    
    if use_placeholder:
        print("\n⚠️  Using placeholder images (--use-placeholder flag set)")
    
    # Load URL mapping
    url_mapping = load_url_mapping()
    if url_mapping:
        print(f"✓ Loaded {len(url_mapping)} image URLs from mapping file")
    elif not use_placeholder:
        if SUPABASE_URL:
            print(f"ℹ️  No URL mapping found. Will construct URLs from SUPABASE_URL")
        else:
            print("⚠️  No URL mapping and SUPABASE_URL not set. Using placeholder images.")
            use_placeholder = True
    
    # Read CSV
    print(f"\nReading: {CSV_FILE}")
    csv_rows = read_csv()
    print(f"✓ Found {len(csv_rows)} products in CSV")
    
    # Convert to JSON format
    print("\nConverting products...")
    products = []
    for i, row in enumerate(csv_rows, 1):
        try:
            product = parse_csv_row(row, url_mapping, use_placeholder)
            products.append(product)
        except Exception as e:
            print(f"  Error parsing row {i}: {e}")
            continue
    
    # Write JSON
    print()
    write_json(products)
    
    # Summary
    print("\n" + "=" * 60)
    print("Conversion Complete!")
    print("=" * 60)
    print(f"\nNext step: Run 'python app/ingestion/ingest_products.py' to load into database")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

