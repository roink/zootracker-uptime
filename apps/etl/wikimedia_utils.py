"""Utility functions for interacting with Wikimedia Commons API."""

from __future__ import annotations

import random
import time
from typing import Any
from urllib.parse import quote

import requests

USER_AGENT = "ZooTracker/1.0 (https://www.zootracker.app; images@zootracker.app)"
HEADERS = {"User-Agent": USER_AGENT}

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

MAX_RETRIES = 3
BASE_BACKOFF = 0.5
REQUEST_TIMEOUT = 30


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter."""
    return BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.25)


def fetch_commons_file_by_mid(mid: str, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any] | None:
    """
    Fetch Commons file metadata using the MediaInfo ID (M-ID).
    
    Args:
        mid: MediaInfo ID (e.g., "M12345")
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with file metadata including:
        - pageid: Commons page ID
        - canonicaltitle: File title (e.g., "File:Example.jpg")
        - url: Direct URL to original file
        - width, height: Image dimensions
        - size: File size in bytes
        - sha1: File hash
        - mime: MIME type
        - timestamp: Upload timestamp
        - user: Uploader username
        - extmetadata: Extended metadata dict
        
        Returns None if the file is not found or an error occurs.
    """
    # Extract numeric page ID from M-ID
    if not mid.startswith("M"):
        return None
    
    try:
        pageid = int(mid[1:])
    except ValueError:
        return None
    
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "imageinfo",
        "iiprop": "url|size|sha1|mime|timestamp|user|extmetadata",
        "pageids": str(pageid),
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                COMMONS_API,
                params=params,
                headers=HEADERS,
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            
            if not data or "query" not in data:
                return None
            
            pages = data["query"].get("pages", [])
            if not pages:
                return None
            
            page = pages[0]
            if page.get("missing"):
                return None
            
            iis = page.get("imageinfo", [])
            if not iis:
                return None
            
            ii = iis[0]
            
            return {
                "pageid": page.get("pageid"),
                "canonicaltitle": page.get("title") or page.get("canonicaltitle"),
                "url": ii.get("url"),
                "width": ii.get("width"),
                "height": ii.get("height"),
                "size": ii.get("size"),
                "sha1": ii.get("sha1"),
                "mime": ii.get("mime"),
                "timestamp": ii.get("timestamp"),
                "user": ii.get("user"),
                "extmetadata": ii.get("extmetadata") or {},
            }
            
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                print(f"  Failed to fetch M-ID {mid} after {MAX_RETRIES} attempts: {e}")
                return None
            time.sleep(_backoff(attempt))
    
    return None


def ensure_file_prefix(name: str) -> str:
    """Ensure a filename has the 'File:' prefix."""
    n = name.strip().replace("_", " ")
    return n if n.lower().startswith("file:") else f"File:{n}"


def commons_page_url_from_title(title: str) -> str:
    """Build the Commons description page URL from 'File:…'."""
    title_norm = title.replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/{quote(title_norm)}"
