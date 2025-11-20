#!/usr/bin/env python3
"""Upload animal images from Wikimedia Commons to Hetzner S3."""

import io
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from PIL import Image

from wikimedia_utils import fetch_commons_file_by_mid, ensure_file_prefix, commons_page_url_from_title

load_dotenv()

# S3 Configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://nbg1.your-objectstorage.com")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "zootracker-public-images")

if not S3_ACCESS_KEY or not S3_SECRET_KEY:
    print("Error: S3_ACCESS_KEY and S3_SECRET_KEY must be set in environment or .env file")
    sys.exit(1)

DB_PATH = Path(__file__).parent / "zootierliste-neu.db"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 30


def get_s3_client():
    """Create and return S3 client."""
    from botocore.config import Config
    
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def get_file_extension(mime_type: str | None, url: str) -> str:
    """Determine file extension from MIME type or URL.
    
    Args:
        mime_type: MIME type from database (may be None)
        url: Original URL to extract extension from as fallback
        
    Returns:
        File extension including leading dot (e.g., ".jpg")
    """
    mime_to_ext = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    
    if mime_type and mime_type in mime_to_ext:
        return mime_to_ext[mime_type]
    
    # Fallback to URL extension
    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if path_ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
        return path_ext if path_ext != ".jpeg" else ".jpg"
    
    return ".jpg"


def download_image(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes:
    """Download image from URL with retries.
    
    Raises:
        requests.HTTPError: If a 404 error occurs on all retries
        RuntimeError: If other errors occur on all retries
    """
    headers = {
        "User-Agent": "ZooTracker/1.0 (https://www.zootracker.app; images@zootracker.app)"
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            return response.content
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                if attempt == MAX_RETRIES - 1:
                    raise
            elif attempt == MAX_RETRIES - 1:
                raise
            print(f"  Retry {attempt + 1}/{MAX_RETRIES} after HTTP error: {e}")
            time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            print(f"  Retry {attempt + 1}/{MAX_RETRIES} after error: {e}")
            time.sleep(RETRY_DELAY * (attempt + 1))
    
    raise RuntimeError(f"Failed to download after {MAX_RETRIES} attempts")


def upload_to_s3(s3_client, bucket: str, s3_path: str, content: bytes, mime_type: str):
    """Upload image content to S3."""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_path,
            Body=content,
            ContentType=mime_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return True
    except ClientError as e:
        print(f"  S3 upload error: {e}")
        return False


def update_s3_path_in_db(conn, mid: str, s3_path: str):
    """Update the s3_path field in the database."""
    conn.execute("UPDATE image SET s3_path = ? WHERE mid = ?", (s3_path, mid))
    conn.commit()


def update_image_metadata_in_db(conn, mid: str, metadata: dict) -> None:
    """Update image metadata in the database from refetched Commons data.
    
    Args:
        conn: Database connection
        mid: MediaInfo ID
        metadata: Dictionary from fetch_commons_file_by_mid
    """
    # Extract and process extmetadata like in fetch_image_links.py
    extm = metadata.get("extmetadata") or {}
    
    def strip_html(text: str) -> str:
        """Very small HTML → plaintext (strip tags, unescape entities)."""
        if not text:
            return ""
        from html import unescape
        no_tags = re.sub(r"<[^>]+>", "", text)
        return unescape(no_tags).strip()
    
    def em(key: str) -> str:
        v = extm.get(key, {})
        if isinstance(v, dict):
            v = v.get("value", "")
        return v or ""
    
    title_txt = strip_html(em("ImageDescription")) or strip_html(em("ObjectName"))
    artist_raw = em("Artist")
    artist_plain = strip_html(artist_raw)
    credit_line = strip_html(em("Credit"))
    usage_terms = strip_html(em("UsageTerms"))
    license_full = em("License")
    license_short = em("LicenseShortName")
    license_url = em("LicenseUrl")
    attr_required = em("AttributionRequired")
    attr_required_int = None
    if attr_required:
        attr_required_int = 1 if attr_required.lower() in {"yes", "true", "1"} else 0
    
    commons_title = ensure_file_prefix(metadata.get("canonicaltitle") or "")
    commons_page_url = commons_page_url_from_title(commons_title)
    
    conn.execute(
        """
        UPDATE image SET
            commons_title = ?,
            commons_page_url = ?,
            original_url = ?,
            width = ?,
            height = ?,
            size_bytes = ?,
            sha1 = ?,
            mime = ?,
            uploaded_at = ?,
            uploader = ?,
            title = ?,
            artist_raw = ?,
            artist_plain = ?,
            license = ?,
            license_short = ?,
            license_url = ?,
            attribution_required = ?,
            usage_terms = ?,
            credit_line = ?,
            extmetadata_json = ?
        WHERE mid = ?
        """,
        (
            commons_title,
            commons_page_url,
            metadata.get("url") or "",
            int(metadata.get("width") or 0),
            int(metadata.get("height") or 0),
            int(metadata.get("size") or 0),
            metadata.get("sha1") or "",
            metadata.get("mime") or "",
            metadata.get("timestamp"),
            metadata.get("user"),
            title_txt or None,
            artist_raw or None,
            artist_plain or None,
            license_full or None,
            license_short or None,
            license_url or None,
            attr_required_int,
            usage_terms or None,
            credit_line or None,
            json.dumps(extm, ensure_ascii=False),
            mid,
        ),
    )
    conn.commit()


def update_variant_s3_path_in_db(conn, mid: str, width: int, s3_path: str):
    """Update the s3_path field for a variant in the database."""
    conn.execute(
        "UPDATE image_variant SET s3_path = ? WHERE mid = ? AND width = ?",
        (s3_path, mid, width)
    )
    conn.commit()


def generate_variant(image_data: bytes, target_width: int, mime_type: str) -> bytes:
    """Generate a resized variant from image data."""
    img = Image.open(io.BytesIO(image_data))
    
    # Convert RGBA to RGB if needed (for JPEG)
    if img.mode == 'RGBA' and mime_type == 'image/jpeg':
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])
        img = rgb_img
    
    # Calculate new dimensions maintaining aspect ratio
    aspect_ratio = img.height / img.width
    target_height = int(target_width * aspect_ratio)
    
    # Only resize if image is larger than target
    if img.width <= target_width:
        return image_data
    
    # Resize image
    resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # Save to bytes
    output = io.BytesIO()
    img_format = 'JPEG' if mime_type == 'image/jpeg' else 'PNG'
    
    if img_format == 'JPEG':
        resized.save(output, format=img_format, quality=85, optimize=True)
    else:
        resized.save(output, format=img_format, optimize=True)
    
    return output.getvalue()


def main():
    """Main upload process for images and variants.
    
    Idempotent: Only processes images that don't have s3_path set.
    
    For SVG images:
    1. Download from Wikimedia
    2. Upload once as animals/{slug}/{mid}.svg (no variants)
    3. Set s3_path to this single file
    
    For raster images (JPEG, PNG, etc):
    1. Download full-size from Wikimedia
    2. Generate and upload all width variants (including original width)
    3. Set s3_path to the LARGEST variant for the "original" image URL
    4. Update DB with all variant S3 paths
    """
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    s3_client = get_s3_client()

    # Get images that haven't been processed yet (no s3_path)
    # This makes the script idempotent - rerun only processes remaining images
    cursor = conn.execute(
        """
        SELECT i.mid, i.animal_art, a.slug as animal_slug, i.original_url, i.mime, 
               i.commons_title, i.width as original_width,
               GROUP_CONCAT(v.width) as variant_widths
        FROM image i
        JOIN animal a ON i.animal_art = a.art
        LEFT JOIN image_variant v ON i.mid = v.mid
        WHERE i.s3_path IS NULL
        GROUP BY i.mid, i.animal_art, a.slug, i.original_url, i.mime, i.commons_title, i.width
        ORDER BY a.slug, i.mid
        """
    )

    images = cursor.fetchall()
    total_images = len(images)

    print(f"S3 Bucket: {S3_BUCKET}")
    print(f"S3 Endpoint: {S3_ENDPOINT}")
    print(f"Found {total_images} images to upload")
    print()

    img_processed = 0
    img_failed = 0
    var_uploaded = 0
    var_failed = 0

    for idx, row in enumerate(images, 1):
        mid = row["mid"]
        animal_slug = row["animal_slug"]
        original_url = row["original_url"]
        mime_type = row["mime"] or "image/jpeg"
        commons_title = row["commons_title"]
        original_width = row["original_width"]
        variant_widths_str = row["variant_widths"]
        
        # Parse variant widths
        variant_widths = []
        if variant_widths_str:
            variant_widths = [int(w) for w in variant_widths_str.split(",")]

        extension = get_file_extension(mime_type, original_url)
        is_svg = mime_type == "image/svg+xml"

        print(f"[{idx}/{total_images}] {mid} ({animal_slug}) - {'SVG' if is_svg else 'Raster'}")
        print(f"  Commons: {commons_title}")

        # Download image from Wikimedia
        image_data = None
        try:
            print("  Downloading from Wikimedia...")
            image_data = download_image(original_url)
            print(f"  Downloaded {len(image_data)} bytes")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                print("  404 Error: Image URL not found. Attempting to refetch from M-ID...")
                # Try to refetch the image metadata from Commons using the M-ID
                refetched_metadata = fetch_commons_file_by_mid(mid)
                if refetched_metadata and refetched_metadata.get("url"):
                    print(f"  Refetched new URL from Commons: {refetched_metadata['url']}")
                    # Update database with new metadata
                    update_image_metadata_in_db(conn, mid, refetched_metadata)
                    # Update local variables for current processing
                    original_url = refetched_metadata["url"]
                    mime_type = refetched_metadata.get("mime") or "image/jpeg"
                    original_width = refetched_metadata.get("width") or original_width
                    extension = get_file_extension(mime_type, original_url)
                    is_svg = mime_type == "image/svg+xml"
                    # Try downloading with the new URL
                    try:
                        image_data = download_image(original_url)
                        print(f"  Downloaded {len(image_data)} bytes from refetched URL")
                    except Exception as e2:
                        print(f"  Download from refetched URL failed: {e2}")
                        img_failed += 1
                        continue
                else:
                    print(f"  Failed to refetch metadata from M-ID {mid}")
                    img_failed += 1
                    continue
            else:
                print(f"  Download failed: {e}")
                img_failed += 1
                continue
        except Exception as e:
            print(f"  Download failed: {e}")
            img_failed += 1
            continue
        
        if image_data is None:
            print("  No image data available, skipping")
            img_failed += 1
            continue

        if is_svg:
            # SVG: Upload once without width suffix
            s3_path = f"animals/{animal_slug}/{mid}{extension}"
            print(f"  Uploading SVG to S3: {s3_path}")
            if upload_to_s3(s3_client, S3_BUCKET, s3_path, image_data, mime_type):
                update_s3_path_in_db(conn, mid, s3_path)
                img_processed += 1
                print("  SVG uploaded successfully")
            else:
                print("  SVG upload failed")
                img_failed += 1
        else:
            # Raster: Generate and upload all variants
            # Include original width if not already in variants
            all_widths = sorted(set(variant_widths + [original_width]))
            print(f"  Variants: {len(all_widths)} to generate (widths: {all_widths})")
            
            largest_variant_path = None
            for width in all_widths:
                variant_s3_path = f"animals/{animal_slug}/{mid}_{width}w{extension}"
                
                try:
                    print(f"    Generating {width}px variant...")
                    variant_data = generate_variant(image_data, width, mime_type)
                    
                    print(f"    Uploading {width}px variant to S3...")
                    if upload_to_s3(s3_client, S3_BUCKET, variant_s3_path, variant_data, mime_type):
                        # Update variant table if this width was in the original variant list
                        if width in variant_widths:
                            update_variant_s3_path_in_db(conn, mid, width, variant_s3_path)
                        var_uploaded += 1
                        # Track the largest variant for the main s3_path
                        largest_variant_path = variant_s3_path
                    else:
                        print(f"    Variant {width}px upload failed")
                        var_failed += 1
                except Exception as e:
                    print(f"    Variant {width}px generation/upload failed: {e}")
                    var_failed += 1
            
            # Set image.s3_path to the largest variant
            if largest_variant_path:
                update_s3_path_in_db(conn, mid, largest_variant_path)
                img_processed += 1
                print("  Raster image complete (s3_path set to largest variant)")
            else:
                print("  Raster image failed (no variants uploaded)")
                img_failed += 1

        # Progress report every 5 images
        if idx % 5 == 0:
            print(f"\nProgress: {idx}/{total_images} ({img_processed} images, {var_uploaded} variants, {img_failed + var_failed} failed)\n")
            time.sleep(0.2)

    conn.close()

    print("\n" + "=" * 60)
    print("Upload complete!")
    print(f"Total images: {total_images}")
    print(f"Images processed: {img_processed}")
    print(f"Images failed: {img_failed}")
    print(f"Variants uploaded: {var_uploaded}")
    print(f"Variants failed: {var_failed}")
    print("=" * 60)
    
    if total_images == 0:
        print("\nAll images already processed! Database is up to date.")
    elif img_failed > 0 or var_failed > 0:
        print("\nRe-run the script to retry failed uploads.")
    else:
        print("\nSuccess! All images and variants uploaded to S3.")


if __name__ == "__main__":
    main()
