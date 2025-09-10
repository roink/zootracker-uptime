#!/usr/bin/env python3
"""Fetch German names for classes, orders and families and store them in SQLite."""

from __future__ import annotations

import argparse
import html
import re
import sqlite3
import time
from typing import Dict, Tuple
from urllib.parse import parse_qs

from bs4 import BeautifulSoup

from zootier_scraper_sqlite import (
    BASE_URL,
    DB_FILE,
    SESSION,
    SLEEP_SECONDS,
    ensure_db_schema,
)

_WS_RE = re.compile(r"\s+")


def ensure_name_tables(conn: sqlite3.Connection) -> None:
    """Create tables for German taxon names if they do not exist."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS klasse_name (
            klasse INTEGER PRIMARY KEY,
            name_de TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ordnung_name (
            ordnung INTEGER PRIMARY KEY,
            klasse INTEGER NOT NULL,
            name_de TEXT,
            FOREIGN KEY (klasse) REFERENCES klasse_name(klasse),
            UNIQUE (klasse, ordnung)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS familie_name (
            familie INTEGER PRIMARY KEY,
            ordnung INTEGER NOT NULL,
            klasse INTEGER NOT NULL,
            name_de TEXT,
            FOREIGN KEY (ordnung) REFERENCES ordnung_name(ordnung),
            UNIQUE (klasse, ordnung, familie)
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ordnung_name_klasse_idx ON ordnung_name(klasse)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS familie_name_ordnung_idx ON familie_name(ordnung)
        """
    )
    conn.commit()


def _clean_label(label: str) -> str:
    """Normalize a label by unescaping HTML entities and collapsing whitespace."""

    return _WS_RE.sub(" ", html.unescape(label)).strip()


def extract_names(
    html: str,
) -> tuple[Dict[int, str], Dict[Tuple[int, int], str], Dict[Tuple[int, int, int], str]]:
    """Extract German names for classes, orders and families from *html*."""

    soup = BeautifulSoup(html, "html.parser")
    nav = soup.find(id="navigation")
    anchors = nav.find_all("a", href=True) if nav else soup.find_all("a", href=True)

    classes: Dict[int, str] = {}
    orders: Dict[Tuple[int, int], str] = {}
    families: Dict[Tuple[int, int, int], str] = {}

    for a in anchors:
        href = a["href"]
        if not href.startswith("?"):
            continue
        qs = parse_qs(href[1:])
        keys = set(qs)
        try:
            if keys == {"klasse"}:
                k = int(qs["klasse"][0])
                classes[k] = _clean_label(a.get_text())
            elif keys == {"klasse", "ordnung"}:
                k = int(qs["klasse"][0])
                o = int(qs["ordnung"][0])
                orders[(k, o)] = _clean_label(a.get_text())
            elif keys == {"klasse", "ordnung", "familie"}:
                k = int(qs["klasse"][0])
                o = int(qs["ordnung"][0])
                f = int(qs["familie"][0])
                families[(k, o, f)] = _clean_label(a.get_text())
        except (ValueError, KeyError, IndexError):
            continue
    return classes, orders, families


def fetch_and_store_names(
    db_path: str = DB_FILE,
    *,
    only_missing: bool = False,
    limit: int | None = None,
) -> None:
    """Fetch German taxon names for all known orders in *db_path* and store them."""

    conn = sqlite3.connect(db_path, timeout=30)
    ensure_db_schema(conn)
    ensure_name_tables(conn)
    cur = conn.cursor()

    cur.execute(
        "SELECT DISTINCT klasse, ordnung FROM animal WHERE klasse IS NOT NULL AND ordnung IS NOT NULL"
    )
    pairs = sorted((int(k), int(o)) for k, o in cur.fetchall())

    if only_missing:
        existing = {row[0] for row in cur.execute("SELECT ordnung FROM ordnung_name")}
        pairs = [(k, o) for k, o in pairs if o not in existing]

    if limit is not None:
        pairs = pairs[:limit]

    for klasse, ordnung in pairs:
        print(f"[+] Fetching klasse={klasse} ordnung={ordnung}...")
        r = SESSION.get(BASE_URL, params={"klasse": klasse, "ordnung": ordnung})
        r.raise_for_status()
        time.sleep(SLEEP_SECONDS)
        classes, orders, families = extract_names(r.text)
        print(f"    → {len(families)} families found")

        for k, name in classes.items():
            cur.execute(
                """
                INSERT INTO klasse_name (klasse, name_de)
                VALUES (?, ?)
                ON CONFLICT(klasse) DO UPDATE SET name_de=excluded.name_de
                """,
                (k, name),
            )
        for (k, o), name in orders.items():
            cur.execute(
                """
                INSERT INTO ordnung_name (ordnung, klasse, name_de)
                VALUES (?, ?, ?)
                ON CONFLICT(ordnung) DO UPDATE SET
                    klasse=excluded.klasse,
                    name_de=excluded.name_de
                """,
                (o, k, name),
            )
        for (k, o, f), name in families.items():
            cur.execute(
                """
                INSERT INTO familie_name (familie, ordnung, klasse, name_de)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(familie) DO UPDATE SET
                    ordnung=excluded.ordnung,
                    klasse=excluded.klasse,
                    name_de=excluded.name_de
                """,
                (f, o, k, name),
            )
        conn.commit()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch German taxon names from zootierliste.de",
    )
    parser.add_argument(
        "--db", default=DB_FILE, help="path to SQLite database (default: %(default)s)",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="skip orders already present in ordnung_name",
    )
    parser.add_argument(
        "--limit", type=int, help="maximum number of orders to fetch",
    )
    args = parser.parse_args()
    fetch_and_store_names(
        args.db,
        only_missing=args.only_missing,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
