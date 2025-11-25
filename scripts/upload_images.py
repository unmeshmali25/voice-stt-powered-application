#!/usr/bin/env python3
"""
Batch upload product images to Supabase Storage.

This script uploads all images from data/images/ to Supabase Storage
and generates a mapping file (data/image_urls.json) with the public URLs.

Usage:
    python scripts/upload_images.py

Requirements:
    - SUPABASE_URL and SUPABASE_KEY environment variables set
    - product-images bucket created in Supabase Storage (public)
    - Images in data/images/ directory
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Support --env flag to load different env files
ENV_FILE = ".env"
if "--staging" in sys.argv or "--env" in sys.argv and "staging" in sys.argv:
    ENV_FILE = ".env.staging"
elif "--production" in sys.argv or "--prod" in sys.argv:
    ENV_FILE = ".env.production"

env_path = Path(__file__).parent.parent / ENV_FILE
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from: {ENV_FILE}")
else:
    load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Support both SUPABASE_KEY and SUPABASE_SERVICE_KEY (service key takes priority)
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
IMAGES_DIR = DATA_DIR / "images"
URL_MAPPING_FILE = DATA_DIR / "image_urls.json"

# Supabase Storage bucket name
BUCKET_NAME = "product-images"

# Supported image extensions
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def get_supabase_client():
    """Initialize and return Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables required.")
        print("\nSet them with:")
        print('  export SUPABASE_URL="https://your-project.supabase.co"')
        print('  export SUPABASE_KEY="your-anon-key"')
        sys.exit(1)
    
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_content_type(filename: str) -> str:
    """Get MIME type for image file."""
    ext = Path(filename).suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return content_types.get(ext, "application/octet-stream")


def get_image_files() -> List[Path]:
    """Get all image files from the images directory."""
    if not IMAGES_DIR.exists():
        print(f"Creating images directory: {IMAGES_DIR}")
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        return []
    
    images = []
    for file in IMAGES_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS:
            images.append(file)
    
    return sorted(images)


def upload_image(supabase, filepath: Path) -> Tuple[str, str, bool]:
    """
    Upload a single image to Supabase Storage.
    
    Returns:
        Tuple of (filename, url, success)
    """
    filename = filepath.name
    content_type = get_content_type(filename)
    
    try:
        with open(filepath, "rb") as f:
            file_data = f.read()
        
        # Upload to Supabase Storage
        result = supabase.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=file_data,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        # Generate public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"
        
        return filename, public_url, True
        
    except Exception as e:
        error_msg = str(e)
        # Handle duplicate file error gracefully
        if "Duplicate" in error_msg or "already exists" in error_msg.lower():
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"
            return filename, public_url, True
        
        print(f"  Error uploading {filename}: {e}")
        return filename, "", False


def load_existing_urls() -> Dict[str, str]:
    """Load existing URL mapping if it exists."""
    if URL_MAPPING_FILE.exists():
        with open(URL_MAPPING_FILE, "r") as f:
            return json.load(f)
    return {}


def save_url_mapping(mapping: Dict[str, str]):
    """Save URL mapping to JSON file."""
    with open(URL_MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"\n✓ URL mapping saved to: {URL_MAPPING_FILE}")


def main():
    """Main upload process."""
    print("=" * 60)
    print("Product Image Upload to Supabase Storage")
    print("=" * 60)
    
    # Get Supabase client
    supabase = get_supabase_client()
    print(f"✓ Connected to Supabase: {SUPABASE_URL}")
    
    # Get image files
    images = get_image_files()
    
    if not images:
        print(f"\nNo images found in {IMAGES_DIR}")
        print("\nTo add images:")
        print(f"  1. Create directory: mkdir -p {IMAGES_DIR}")
        print(f"  2. Add your product images to: {IMAGES_DIR}")
        print("  3. Run this script again")
        return 0
    
    print(f"\nFound {len(images)} images to upload")
    print(f"Bucket: {BUCKET_NAME}")
    print("-" * 60)
    
    # Load existing URLs
    url_mapping = load_existing_urls()
    
    # Upload images
    success_count = 0
    error_count = 0
    
    for i, image_path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] Uploading {image_path.name}...", end=" ")
        
        filename, url, success = upload_image(supabase, image_path)
        
        if success:
            url_mapping[filename] = url
            print("✓")
            success_count += 1
        else:
            print("✗")
            error_count += 1
    
    # Save URL mapping
    if url_mapping:
        save_url_mapping(url_mapping)
    
    # Summary
    print("\n" + "=" * 60)
    print("Upload Summary")
    print("=" * 60)
    print(f"  Successful: {success_count}")
    print(f"  Failed: {error_count}")
    print(f"  Total: {len(images)}")
    
    if error_count > 0:
        print("\n⚠️  Some uploads failed. Check errors above.")
        return 1
    
    print("\n✅ All images uploaded successfully!")
    print(f"\nNext step: Run 'python scripts/csv_to_json.py' to generate products.json")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

