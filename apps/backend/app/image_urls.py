"""Image URL generation utilities."""

from __future__ import annotations

from . import config


def get_image_url(original_url: str, s3_path: str | None, mime: str | None = None) -> str:
    """Generate image URL based on environment configuration.

    In development (WIKIMEDIA mode), returns the original Wikimedia URL.
    In production (S3 mode), returns the proxied S3 URL via /assets/.

    For raster images, s3_path points to the largest variant (with width suffix).
    For SVG images, s3_path points to the single SVG file (no width suffix).

    Args:
        original_url: Original Wikimedia Commons URL
        s3_path: S3 bucket path (e.g., "animals/slug/M123_2388w.jpg" or "animals/slug/M123.svg")
        mime: MIME type of the image (used to detect SVG)

    Returns:
        URL string to use in API responses
    """
    if config.IMAGE_URL_MODE == "S3" and s3_path:
        base = config.SITE_BASE_URL.rstrip("/")
        return f"{base}/assets/{s3_path}"

    return original_url


def get_variant_url(
    thumb_url: str, variant_s3_path: str | None, image_s3_path: str | None = None, mime: str | None = None
) -> str:
    """Generate image variant URL based on environment configuration.

    In development (WIKIMEDIA mode), returns the Wikimedia thumbnail URL.
    In production (S3 mode), returns the S3 variant URL for rasters, or the
    single SVG URL for vector images (SVGs don't need variants).

    Args:
        thumb_url: Original Wikimedia thumbnail URL
        variant_s3_path: S3 path for this specific variant (raster only)
        image_s3_path: S3 path for the main image (used for SVG fallback)
        mime: MIME type of the image (used to detect SVG)

    Returns:
        URL string to use in API responses
    """
    if config.IMAGE_URL_MODE == "S3":
        # For SVG, return the main image path (no variants)
        if mime == "image/svg+xml" and image_s3_path:
            base = config.SITE_BASE_URL.rstrip("/")
            return f"{base}/assets/{image_s3_path}"
        # For raster images, use the specific variant
        if variant_s3_path:
            base = config.SITE_BASE_URL.rstrip("/")
            return f"{base}/assets/{variant_s3_path}"

    return thumb_url
