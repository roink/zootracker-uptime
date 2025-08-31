#!/usr/bin/env python3
"""Utilities to normalize and enrich Latin animal names in the SQLite database.

This script adds additional columns to the ``animal`` table based on the existing
``latin_name`` column. It relies on :func:`latin_name_parser.parse_latin_name`
to extract a canonical name, alternative spellings, qualifiers, locality labels
and trade codes. The main entry point for reprocessing an existing database is
:func:`update_animals` which can be executed as a script.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Optional

from zootier_scraper_sqlite import DB_FILE, ensure_db_schema
from latin_name_parser import parse_latin_name

def update_animals(conn: sqlite3.Connection) -> None:
    """Populate normalized name columns for all rows in ``animal``."""

    cur = conn.cursor()
    for art, latin in cur.execute("SELECT art, latin_name FROM animal"):
        parsed = parse_latin_name(latin)
        cur.execute(
            """
            UPDATE animal SET
                normalized_latin_name = ?,
                alternative_latin_names = ?,
                qualifier = ?,
                qualifier_target = ?,
                locality = ?,
                trade_code = ?
            WHERE art = ?
            """,
            (
                parsed.normalized,
                json.dumps(parsed.alternative_names, ensure_ascii=False),
                parsed.qualifier,
                parsed.qualifier_target,
                parsed.locality,
                parsed.trade_code,
                art,
            ),
        )
    conn.commit()

def main(db_path: Optional[str] = None) -> None:
    db_path = db_path or DB_FILE
    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    update_animals(conn)
    conn.close()

if __name__ == "__main__":  # pragma: no cover - manual invocation
    parser = argparse.ArgumentParser(
        description="Normalize Latin names into extra columns",
    )
    parser.add_argument(
        "--db",
        help="Path to SQLite database (defaults to zootier_scraper_sqlite.DB_FILE)",
    )
    args = parser.parse_args()
    main(args.db)
