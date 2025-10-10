
#!/usr/bin/env python3
"""
Google Places lookup: free-text search -> lat/lng

Two modes:
1) Default (cheaper): Text Search (IDs-only) -> Place Details (location only)
2) --one-call (simpler, pricier): Text Search Pro returning location directly

Auth:
  Set environment variable GOOGLE_MAPS_API_KEY with a Places API (new) key.

Usage examples:
  # Cheapest two-step with a soft location bias (50 km around point):
  python google_places_lookup.py "Sun City Predator World" --bias-circle -25.73 27.09 50000

  # Restrict search to a rectangle (south, west, north, east):
  python google_places_lookup.py "Sun City Predator World" --restrict-rect -26.1 26.8 -25.4 27.5

  # One-call mode (Text Search Pro: returns location directly):
  python google_places_lookup.py "Sun City Predator World" --one-call --bias-circle -25.73 27.09 50000

Outputs a compact JSON object with name, place_id, latitude, longitude.
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional, Tuple
import requests

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL_TMPL = "https://places.googleapis.com/v1/places/{place_id}"

# ---------- Helpers ----------

class ApiError(RuntimeError):
    pass

def _headers(api_key: str, field_mask: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }

def _retry_request(method: str, url: str, headers: Dict[str, str], json_body: Dict[str, Any]) -> Dict[str, Any]:
    # Simple exponential backoff for 429/5xx
    backoff = 0.5
    for attempt in range(6):
        resp = requests.request(method, url, headers=headers, json=json_body, timeout=20)
        if resp.status_code < 400:
            try:
                return resp.json()
            except Exception as e:
                raise ApiError(f"Invalid JSON from API: {e}: {resp.text[:200]}")
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 8.0)
            continue
        # Other client errors: show body for diagnostics
        raise ApiError(f"API error {resp.status_code}: {resp.text[:500]}")
    raise ApiError("API retries exhausted.")

def _retry_get(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    backoff = 0.5
    for attempt in range(6):
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code < 400:
            try:
                return resp.json()
            except Exception as e:
                raise ApiError(f"Invalid JSON from API: {e}: {resp.text[:200]}")
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 8.0)
            continue
        raise ApiError(f"API error {resp.status_code}: {resp.text[:500]}")
    raise ApiError("API retries exhausted.")

# ---------- Payload builders ----------

def make_location_bias(args) -> Optional[Dict[str, Any]]:
    if args.restrict_rect or args.restrict_circle:
        return None  # mutually exclusive with restriction (we enforce in argparse)
    if args.bias_circle:
        lat, lng, radius = args.bias_circle
        return {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": int(radius)}}
    if args.bias_rect:
        s, w, n, e = args.bias_rect
        return {"rectangle": {"low": {"latitude": s, "longitude": w},
                              "high": {"latitude": n, "longitude": e}}}
    return None

def make_location_restriction(args) -> Optional[Dict[str, Any]]:
    if args.restrict_circle:
        lat, lng, radius = args.restrict_circle
        return {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": int(radius)}}
    if args.restrict_rect:
        s, w, n, e = args.restrict_rect
        return {"rectangle": {"low": {"latitude": s, "longitude": w},
                              "high": {"latitude": n, "longitude": e}}}
    return None

# ---------- Core calls ----------

def text_search_ids_only(api_key: str, query: str, args) -> Dict[str, Any]:
    field_mask = "places.id,places.name"
    headers = _headers(api_key, field_mask)
    body: Dict[str, Any] = {"textQuery": query}
    lb = make_location_bias(args)
    lr = make_location_restriction(args)
    if lb and lr:
        raise ValueError("locationBias and locationRestriction are mutually exclusive.")
    if lb:
        body["locationBias"] = lb
    if lr:
        body["locationRestriction"] = lr
    return _retry_request("POST", TEXT_SEARCH_URL, headers, body)

def text_search_with_location(api_key: str, query: str, args) -> Dict[str, Any]:
    # One-call mode (Text Search Pro) asks directly for places.location
    field_mask = "places.id,places.name,places.location"
    headers = _headers(api_key, field_mask)
    body: Dict[str, Any] = {"textQuery": query}
    lb = make_location_bias(args)
    lr = make_location_restriction(args)
    if lb and lr:
        raise ValueError("locationBias and locationRestriction are mutually exclusive.")
    if lb:
        body["locationBias"] = lb
    if lr:
        body["locationRestriction"] = lr
    return _retry_request("POST", TEXT_SEARCH_URL, headers, body)

def place_details_location(api_key: str, place_id: str) -> Dict[str, Any]:
    field_mask = "id,location,name"
    headers = _headers(api_key, field_mask)
    url = DETAILS_URL_TMPL.format(place_id=place_id)
    return _retry_get(url, headers)

# ---------- Public API ----------

def lookup_coords(query: str, one_call: bool = False, **kwargs) -> Dict[str, Any]:
    """
    Programmatic API: lookup_coords("query", one_call=False, bias_circle=(-25.73, 27.09, 50000), ...)
    Returns: {"name": str, "place_id": str, "latitude": float, "longitude": float, "source": "details"|"text_search_pro"}
    """
    class _Args:  # quick shim for builder functions
        def __init__(self, **k): self.__dict__.update(k)
        def __getattr__(self, item): return self.__dict__.get(item)

    args = _Args(**kwargs)
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") or ""
    if not api_key:
        raise ApiError("Missing GOOGLE_MAPS_API_KEY in environment.")

    if one_call:
        ts = text_search_with_location(api_key, query, args)
        places = ts.get("places") or []
        if not places:
            raise ApiError("No results from Text Search.")
        p0 = places[0]
        loc = (p0.get("location") or {}).get("latLng") or {}
        if "latitude" not in loc or "longitude" not in loc:
            raise ApiError("Text Search did not return location for the top result.")
        return {
            "name": p0.get("name"),
            "place_id": p0.get("id"),
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "source": "text_search_pro",
        }

    # Two-step: IDs-only -> Details (location)
    ts = text_search_ids_only(api_key, query, args)
    places = ts.get("places") or []
    print(places)
    if not places:
        raise ApiError("No results from Text Search (IDs only).")
    place_id = places[0].get("id")
    print(place_id)
    if not place_id:
        raise ApiError("Top result missing place id.")
    det = place_details_location(api_key, place_id)
    # Places API (New) details: same LatLng shape as above.
    loc = (det.get("location") or {})
    if "latitude" not in loc or "longitude" not in loc:
        loc = loc.get("latLng") or {}
    if "latitude" not in loc or "longitude" not in loc:
        raise ApiError("Place Details did not return location.")
    return {
        "name": det.get("name"),
        "place_id": det.get("id"),
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "source": "details",
    }

# ---------- CLI ----------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Google Places lookup for coordinates")
    p.add_argument("query", help="Free-text search (e.g., 'Sun City Predator World')")
    # Bias (soft)
    p.add_argument("--bias-circle", nargs=3, type=float, metavar=("LAT", "LNG", "RADIUS_M"),
                   help="Location bias as circle with radius in meters")
    p.add_argument("--bias-rect", nargs=4, type=float, metavar=("S", "W", "N", "E"),
                   help="Location bias as rectangle (south, west, north, east)")
    # Restriction (hard)
    p.add_argument("--restrict-circle", nargs=3, type=float, metavar=("LAT", "LNG", "RADIUS_M"),
                   help="Location restriction as circle with radius in meters")
    p.add_argument("--restrict-rect", nargs=4, type=float, metavar=("S", "W", "N", "E"),
                   help="Location restriction as rectangle (south, west, north, east)")
    p.add_argument("--one-call", action="store_true", help="Use Text Search Pro to return location directly (costs more)")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = p.parse_args(argv)

    # Enforce mutual exclusivity: any bias* with any restrict* is not allowed
    if (args.bias_circle or args.bias_rect) and (args.restrict_circle or args.restrict_rect):
        p.error("locationBias and locationRestriction are mutually exclusive; choose one.")
    return args

def main(argv=None):
    args = parse_args(argv)
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("ERROR: Set GOOGLE_MAPS_API_KEY in your environment.", file=sys.stderr)
        sys.exit(2)
    try:
        result = lookup_coords(
            args.query,
            one_call=args.one_call,
            bias_circle=tuple(args.bias_circle) if args.bias_circle else None,
            bias_rect=tuple(args.bias_rect) if args.bias_rect else None,
            restrict_circle=tuple(args.restrict_circle) if args.restrict_circle else None,
            restrict_rect=tuple(args.restrict_rect) if args.restrict_rect else None,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}), flush=True)
        sys.exit(1)

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
