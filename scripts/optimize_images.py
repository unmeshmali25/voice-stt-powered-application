#!/usr/bin/env python3
"""
Script to optimize product images for web delivery.
Resizes images to max 800px width and compresses to 80% quality.
"""

import os
import shutil
from pathlib import Path
from PIL import Image
import sys

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
IMAGES_DIR = PROJECT_ROOT / "data" / "images"
BACKUP_DIR = PROJECT_ROOT / "data" / "images_original"

# Optimization settings
MAX_WIDTH = 800
MAX_HEIGHT = 800
QUALITY = 80  # JPEG quality (1-100)
TARGET_SIZE_KB = 100  # Target max size


def ensure_backup():
    """Create backup of original images"""
    if not BACKUP_DIR.exists():
        print(f"💾 Creating backup directory: {BACKUP_DIR}")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Copy all images to backup
        for image_file in IMAGES_DIR.glob("*"):
            if image_file.is_file() and image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                shutil.copy2(image_file, BACKUP_DIR / image_file.name)

        print(f"✅ Backed up {len(list(BACKUP_DIR.glob('*')))} images")
    else:
        print(f"✅ Backup already exists at: {BACKUP_DIR}")


def get_file_size_kb(filepath):
    """Get file size in KB"""
    return os.path.getsize(filepath) / 1024


def optimize_image(image_path):
    """Optimize a single image"""
    try:
        # Get original size
        original_size = get_file_size_kb(image_path)

        # Open image
        with Image.open(image_path) as img:
            # Convert RGBA to RGB if needed (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background

            # Get current dimensions
            width, height = img.size

            # Calculate new dimensions (maintain aspect ratio)
            if width > MAX_WIDTH or height > MAX_HEIGHT:
                if width > height:
                    new_width = MAX_WIDTH
                    new_height = int((MAX_WIDTH / width) * height)
                else:
                    new_height = MAX_HEIGHT
                    new_width = int((MAX_HEIGHT / height) * width)

                # Resize with high-quality resampling
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                resized = True
            else:
                resized = False

            # Save optimized image
            img.save(
                image_path,
                'JPEG',
                quality=QUALITY,
                optimize=True,
                progressive=True  # Progressive JPEG for better web loading
            )

        # Get new size
        new_size = get_file_size_kb(image_path)
        reduction = ((original_size - new_size) / original_size * 100) if original_size > 0 else 0

        return {
            'success': True,
            'original_size': original_size,
            'new_size': new_size,
            'reduction': reduction,
            'resized': resized
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def optimize_all_images():
    """Optimize all images in the images directory"""

    if not IMAGES_DIR.exists():
        print(f"❌ Images directory not found: {IMAGES_DIR}")
        return

    # Ensure backup exists
    ensure_backup()

    # Get all image files
    image_files = [
        f for f in IMAGES_DIR.glob("*")
        if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ]

    print(f"\n{'='*80}")
    print(f"🎨 IMAGE OPTIMIZATION")
    print(f"{'='*80}")
    print(f"Images to process: {len(image_files)}")
    print(f"Max dimensions: {MAX_WIDTH}x{MAX_HEIGHT}px")
    print(f"JPEG quality: {QUALITY}%")
    print(f"\n{'='*80}\n")

    results = []
    total_original_size = 0
    total_new_size = 0
    errors = []

    for i, image_path in enumerate(image_files, 1):
        print(f"[{i}/{len(image_files)}] Processing: {image_path.name}...", end=" ")

        result = optimize_image(image_path)

        if result['success']:
            results.append(result)
            total_original_size += result['original_size']
            total_new_size += result['new_size']

            status = "✨ RESIZED" if result['resized'] else "✓ OPTIMIZED"
            print(f"{status} | {result['original_size']:.1f}KB → {result['new_size']:.1f}KB ({result['reduction']:.1f}% reduction)")
        else:
            errors.append({'file': image_path.name, 'error': result['error']})
            print(f"❌ FAILED: {result['error']}")

    # Summary
    print(f"\n{'='*80}")
    print(f"📊 OPTIMIZATION SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successfully optimized: {len(results)}/{len(image_files)} images")
    print(f"❌ Errors: {len(errors)}")

    if results:
        print(f"\n💾 Storage Impact:")
        print(f"   Original total: {total_original_size:.2f} KB ({total_original_size/1024:.2f} MB)")
        print(f"   Optimized total: {total_new_size:.2f} KB ({total_new_size/1024:.2f} MB)")
        print(f"   Total saved: {total_original_size - total_new_size:.2f} KB ({(total_original_size - total_new_size)/1024:.2f} MB)")
        print(f"   Reduction: {((total_original_size - total_new_size) / total_original_size * 100):.1f}%")

        # Find largest files
        sorted_results = sorted(
            [(img.name, get_file_size_kb(img)) for img in image_files],
            key=lambda x: x[1],
            reverse=True
        )

        print(f"\n🔝 Largest optimized images:")
        for i, (name, size) in enumerate(sorted_results[:5], 1):
            status = "⚠️" if size > TARGET_SIZE_KB else "✅"
            print(f"   {status} {i}. {name}: {size:.1f} KB")

    if errors:
        print(f"\n❌ Errors encountered:")
        for error in errors:
            print(f"   • {error['file']}: {error['error']}")

    print(f"\n{'='*80}")
    print(f"✅ OPTIMIZATION COMPLETE!")
    print(f"{'='*80}")
    print(f"Backup location: {BACKUP_DIR}")


if __name__ == "__main__":
    print("🎨 Image Optimization Script")
    print("="*80)

    # Check if Pillow is installed
    try:
        import PIL
    except ImportError:
        print("❌ Error: Pillow library not found!")
        print("Please install it with: pip install Pillow")
        sys.exit(1)

    optimize_all_images()
