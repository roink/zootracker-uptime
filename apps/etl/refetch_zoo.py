#!/usr/bin/env python3
"""Refetch information for a zoo and store it in the SQLite database."""
import argparse
import sqlite3
import time
from bs4 import BeautifulSoup
import requests

from zootier_scraper_sqlite import (
    DB_FILE,
    MAP_ZOOS_URL,
    SLEEP_SECONDS,
    ensure_db_schema,
    parse_zoo_popup,
    fetch_zoo_popup_soup,
    parse_zoo_map,
    SESSION,
    ZooLocation,
    with_retry,
)


def fetch_zoo_location(zoo_id: int, session: requests.Session | None = None) -> ZooLocation:
    """Fetch the latitude/longitude for a single zoo id."""
    sess = session or SESSION
    r = sess.get(MAP_ZOOS_URL, params={"showzoo": str(zoo_id)}, timeout=(5, 20))
    r.raise_for_status()
    time.sleep(SLEEP_SECONDS)
    soup = BeautifulSoup(r.text, "html.parser")
    locations = parse_zoo_map(soup)
    for loc in locations:
        if loc.zoo_id == zoo_id:
            return loc
    raise ValueError(f"Location for zoo {zoo_id} not found")


def refetch_zoo(zoo_id: int, db_path: str = DB_FILE) -> None:
    """Refetch info for the given zoo id and update the database."""
    conn = sqlite3.connect(db_path, timeout=30)
    ensure_db_schema(conn)
    location = fetch_zoo_location(zoo_id)
    info = parse_zoo_popup(fetch_zoo_popup_soup(zoo_id))
    cur = conn.cursor()
    with conn:
        with_retry(
            cur.execute,
            """
            INSERT INTO zoo (zoo_id, continent, country, city, name, latitude, longitude, website)
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(zoo_id) DO UPDATE SET
                country=excluded.country,
                city=excluded.city,
                name=excluded.name,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                website=excluded.website
            """,
            (
                zoo_id,
                info.country,
                info.city,
                info.name,
                location.latitude,
                location.longitude,
                info.website,
            ),
        )
    conn.close()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Refetch info for a zoo and store in the DB")
    parser.add_argument("zoo_id", type=int, help="Numeric zoo identifier")
    parser.add_argument("--db", default=DB_FILE, help="Path to SQLite database file")
    args = parser.parse_args()
    refetch_zoo(args.zoo_id, args.db)


if __name__ == "__main__":
    main()
