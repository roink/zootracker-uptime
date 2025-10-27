"""Helpers for constructing absolute URLs used in public endpoints."""

from __future__ import annotations

from ..config import SITE_BASE_URL


def build_absolute_url(path: str) -> str:
    """Join the configured site base URL with a relative path."""

    base = SITE_BASE_URL.rstrip("/")
    suffix = path.lstrip("/")
    if not suffix:
        return base or ""
    if not base:
        return f"/{suffix}"
    return f"{base}/{suffix}"
