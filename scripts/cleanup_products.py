#!/usr/bin/env python3
"""
Script to remove products from CSV that don't have corresponding images.
This ensures all products in the CSV have valid images before sync.
"""

import csv
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CSV_FILE = PROJECT_ROOT / "data" / "products.csv"
IMAGES_DIR = PROJECT_ROOT / "data" / "images"
BACKUP_FILE = PROJECT_ROOT / "data" / "products_backup.csv"


def get_available_images():
    """Get set of all image filenames in data/images/"""
    if not IMAGES_DIR.exists():
        print(f"❌ Images directory not found: {IMAGES_DIR}")
        return set()

    images = set()
    for file in IMAGES_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            images.add(file.name)

    return images


def cleanup_products():
    """Remove products without corresponding images"""

    # Get available images
    available_images = get_available_images()
    print(f"📁 Found {len(available_images)} images in {IMAGES_DIR}")

    # Read CSV
    if not CSV_FILE.exists():
        print(f"❌ CSV file not found: {CSV_FILE}")
        return

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_products = list(reader)

    print(f"📄 Loaded {len(all_products)} products from CSV")

    # Filter products with images
    products_with_images = []
    products_without_images = []

    for product in all_products:
        image_filename = product['image_filename']
        if image_filename in available_images:
            products_with_images.append(product)
        else:
            products_without_images.append(product)

    # Summary
    print(f"\n{'='*70}")
    print(f"📊 CLEANUP SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Products WITH images:    {len(products_with_images)}")
    print(f"❌ Products WITHOUT images: {len(products_without_images)}")

    if products_without_images:
        print(f"\n🗑️  PRODUCTS TO BE REMOVED:")
        print(f"{'-'*70}")
        for i, product in enumerate(products_without_images, 1):
            print(f"{i:3}. {product['name']}")
            print(f"     Missing: {product['image_filename']}")

    # Backup original CSV
    print(f"\n💾 Creating backup at: {BACKUP_FILE}")
    with open(BACKUP_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(all_products)

    # Write cleaned CSV
    print(f"✍️  Writing cleaned CSV to: {CSV_FILE}")
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(products_with_images)

    print(f"\n{'='*70}")
    print(f"✅ CLEANUP COMPLETE!")
    print(f"{'='*70}")
    print(f"Final product count: {len(products_with_images)}")
    print(f"Removed: {len(products_without_images)} products")
    print(f"Backup saved to: products_backup.csv")

    return len(products_with_images), len(products_without_images)


if __name__ == "__main__":
    print("🧹 Product CSV Cleanup Script")
    print("="*70)
    cleanup_products()
