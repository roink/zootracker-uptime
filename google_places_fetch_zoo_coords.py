#!/usr/bin/env python3
"""Populate Google-based coordinates for zoos.

This script augments the ``zoo`` table with additional latitude/longitude
columns sourced from Google Maps. Existing ``latitude``/``longitude`` values
remain untouched; the new values are stored in ``latitude_google`` and
``longitude_google``.

For every zoo where either of the Google columns is ``NULL`` the script runs a
Places Text Search for "{name} {city}". If the database already contains
coordinates, they are used as a soft bias (50 km radius) to guide the search.

Usage example::

    python google_places_fetch_zoo_coords.py --db path/to/zootierliste.db --limit 20

Environment::

    GOOGLE_MAPS_API_KEY must be set with access to the Places API.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Iterable, Optional, Sequence, Tuple

from google_places_lookup import ApiError, lookup_coords
from zootier_scraper_sqlite import DB_FILE

GOOGLE_RADIUS_METERS = 50_000


def ensure_google_columns(conn: sqlite3.Connection) -> None:
    """Create latitude_google/longitude_google columns if they do not exist."""

    cur = conn.execute("PRAGMA table_info(zoo)")
    columns = {row[1] for row in cur.fetchall()}
    statements: list[str] = []
    if "latitude_google" not in columns:
        statements.append("ALTER TABLE zoo ADD COLUMN latitude_google REAL")
    if "longitude_google" not in columns:
        statements.append("ALTER TABLE zoo ADD COLUMN longitude_google REAL")
    for stmt in statements:
        conn.execute(stmt)
    if statements:
        conn.commit()


def load_target_rows(conn: sqlite3.Connection, limit: Optional[int]) -> Sequence[sqlite3.Row]:
    """Fetch zoos requiring Google coordinates ordered by species_count desc."""

    base_query = (
        "SELECT zoo_id, name, city, latitude, longitude, species_count, "
        "latitude_google, longitude_google "
        "FROM zoo "
        "WHERE latitude_google IS NULL OR longitude_google IS NULL "
        "ORDER BY species_count DESC, zoo_id ASC"
    )
    if limit is not None:
        base_query += " LIMIT ?"
        rows = conn.execute(base_query, (limit,)).fetchall()
    else:
        rows = conn.execute(base_query).fetchall()
    return rows


def build_query(row: sqlite3.Row) -> Optional[str]:
    parts = [part.strip() for part in (row["name"], row["city"]) if part]
    if not parts:
        return None
    return " ".join(parts)


def make_bias(row: sqlite3.Row) -> Optional[Tuple[float, float, int]]:
    lat = row["latitude"]
    lng = row["longitude"]
    if lat is None or lng is None:
        return None
    return float(lat), float(lng), GOOGLE_RADIUS_METERS


def update_google_coordinates(
    conn: sqlite3.Connection,
    rows: Iterable[sqlite3.Row],
    *,
    dry_run: bool,
) -> int:
    success_count = 0
    for row in rows:
        query = build_query(row)
        zoo_id = row["zoo_id"]
        if not query:
            print(f"[SKIP] Zoo {zoo_id}: missing name/city", file=sys.stderr)
            continue
        kwargs = {}
        bias = make_bias(row)
        if bias:
            kwargs["bias_circle"] = bias
        try:
            result = lookup_coords(query, **kwargs)
        except ApiError as exc:
            print(f"[FAIL] Zoo {zoo_id} ({query}): {exc}", file=sys.stderr)
            continue
        lat = result["latitude"]
        lng = result["longitude"]
        print(
            f"[OK] Zoo {zoo_id}: {query} -> lat={lat:.6f}, lng={lng:.6f} "
            f"(source={result.get('source')})"
        )
        success_count += 1
        if not dry_run:
            conn.execute(
                "UPDATE zoo SET latitude_google=?, longitude_google=? WHERE zoo_id=?",
                (lat, lng, zoo_id),
            )
            conn.commit()
    return success_count


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Google Maps coordinates for zoos and store them in the database."
    )
    parser.add_argument("--db", default=DB_FILE, help="Path to SQLite database (default: %(default)s)")
    parser.add_argument("--limit", type=int, help="Maximum number of zoos to process")
    parser.add_argument("--dry-run", action="store_true", help="Fetch coordinates without updating the DB")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        ensure_google_columns(conn)
        rows = load_target_rows(conn, args.limit)
        if not rows:
            print("No zoos require Google coordinates.")
            return 0
        updated = update_google_coordinates(conn, rows, dry_run=args.dry_run)
        if args.dry_run:
            print(f"Dry run complete – {updated} updates ready.")
        else:
            print(f"Updated {updated} zoos with Google coordinates.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
