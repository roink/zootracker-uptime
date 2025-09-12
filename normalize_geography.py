#!/usr/bin/env python3
"""Normalize continent and country names into lookup tables.

This script extracts unique continent and country names from a zoo table,
creates ``continent_name`` and ``country_name`` tables with German and optional
English name columns, and replaces the textual values in the ``zoo`` table with
integer IDs referencing those lookup tables.
"""

from __future__ import annotations

import argparse
import sqlite3
from typing import Dict, Iterable, List, Tuple

from copy_zoo_metadata import get_existing_columns


def ensure_lookup_tables(conn: sqlite3.Connection) -> None:
    """Ensure that the continent and country lookup tables exist."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS continent_name (
            id INTEGER PRIMARY KEY,
            name_de TEXT NOT NULL UNIQUE,
            name_en TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS country_name (
            id INTEGER PRIMARY KEY,
            name_de TEXT NOT NULL UNIQUE,
            name_en TEXT,
            continent_id INTEGER REFERENCES continent_name(id)
        )
        """
    )


def collect_distinct_values(
    conn: sqlite3.Connection, table: str, column: str
) -> list[str]:
    """Return sorted list of distinct non-empty values from ``table.column``."""
    cur = conn.execute(
        f'SELECT DISTINCT "{column}" FROM "{table}" '
        f'WHERE "{column}" IS NOT NULL AND "{column}" <> "" ORDER BY "{column}"'
    )
    return [row[0] for row in cur.fetchall()]


def populate_lookup(
    conn: sqlite3.Connection, table: str, names: Iterable[str]
) -> Dict[str, int]:
    """Insert ``names`` into ``table`` and return a mapping name -> id."""
    cur = conn.execute(f'SELECT id, name_de FROM "{table}"')
    existing = {row[1]: row[0] for row in cur.fetchall()}
    to_insert = [(name,) for name in names if name not in existing]
    with conn:
        conn.executemany(
            f'INSERT OR IGNORE INTO "{table}" (name_de) VALUES (?)', to_insert
        )
    cur = conn.execute(f'SELECT id, name_de FROM "{table}"')
    return {row[1]: row[0] for row in cur.fetchall()}


def collect_country_continent_pairs(
    conn: sqlite3.Connection, zoo_table: str
) -> List[Tuple[str, str]]:
    """Return unique ``(country, continent)`` pairs from ``zoo_table``."""
    cur = conn.execute(
        f'SELECT DISTINCT country, continent FROM "{zoo_table}" '
        'WHERE country IS NOT NULL AND country <> "" '
        'AND continent IS NOT NULL AND continent <> "" '
        'ORDER BY country, continent'
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def populate_countries(
    conn: sqlite3.Connection,
    pairs: Iterable[Tuple[str, str]],
    continent_map: Dict[str, int],
) -> Dict[str, int]:
    """Insert countries with their continent IDs and return name -> id mapping."""
    cur = conn.execute('SELECT id, name_de FROM country_name')
    existing = {row[1]: row[0] for row in cur.fetchall()}
    to_insert = [
        (country, continent_map[continent])
        for country, continent in pairs
        if country not in existing
    ]
    with conn:
        conn.executemany(
            'INSERT OR IGNORE INTO country_name (name_de, continent_id) VALUES (?, ?)',
            to_insert,
        )
        for country, continent in pairs:
            continent_id = continent_map[continent]
            conn.execute(
                'UPDATE country_name SET continent_id = ? WHERE name_de = ?',
                (continent_id, country),
            )
    cur = conn.execute('SELECT id, name_de FROM country_name')
    return {row[1]: row[0] for row in cur.fetchall()}


def replace_zoo_values(
    conn: sqlite3.Connection,
    zoo_table: str,
    src_column: str,
    dst_column: str,
    mapping: Dict[str, int],
) -> None:
    """Fill ``dst_column`` with IDs based on matching ``src_column`` values."""
    with conn:
        conn.executemany(
            f'UPDATE "{zoo_table}" SET "{dst_column}" = ? WHERE "{src_column}" = ?',
            [(id_, name) for name, id_ in mapping.items()],
        )


def normalize_geography(
    conn: sqlite3.Connection, zoo_table: str = "zoo"
) -> None:
    """Normalize continent and country names for ``zoo_table``."""
    conn.execute("PRAGMA foreign_keys=ON")
    cols = set(get_existing_columns(conn, zoo_table))
    for required in ("continent", "country"):
        if required not in cols:
            raise SystemExit(f"Table '{zoo_table}' missing column '{required}'")

    ensure_lookup_tables(conn)

    continent_names = collect_distinct_values(conn, zoo_table, "continent")
    continent_map = populate_lookup(conn, "continent_name", continent_names)

    country_pairs = collect_country_continent_pairs(conn, zoo_table)
    country_map = populate_countries(conn, country_pairs, continent_map)

    # Add new integer columns and fill them
    with conn:
        conn.execute(
            f'ALTER TABLE "{zoo_table}" ADD COLUMN continent_id INTEGER REFERENCES continent_name(id)'
        )
        conn.execute(
            f'ALTER TABLE "{zoo_table}" ADD COLUMN country_id INTEGER REFERENCES country_name(id)'
        )

    replace_zoo_values(conn, zoo_table, "continent", "continent_id", continent_map)
    replace_zoo_values(conn, zoo_table, "country", "country_id", country_map)

    # Drop indexes that reference the soon-to-be-removed columns
    cur = conn.execute(f'PRAGMA index_list("{zoo_table}")')
    for row in cur.fetchall():
        idx_name = row[1]
        info = conn.execute(f'PRAGMA index_info("{idx_name}")').fetchall()
        cols = [i[2] for i in info]
        if any(col in {"continent", "country"} for col in cols):
            with conn:
                conn.execute(f'DROP INDEX "{idx_name}"')

    # Drop old text columns and rename the new ID columns
    with conn:
        conn.execute(f'ALTER TABLE "{zoo_table}" DROP COLUMN continent')
        conn.execute(f'ALTER TABLE "{zoo_table}" DROP COLUMN country')
        conn.execute(f'ALTER TABLE "{zoo_table}" RENAME COLUMN continent_id TO continent')
        conn.execute(f'ALTER TABLE "{zoo_table}" RENAME COLUMN country_id TO country')


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Move continent and country names to lookup tables and "
            "store IDs in the zoo table"
        )
    )
    ap.add_argument("db_path")
    ap.add_argument("--zoo-table", default="zoo")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path)
    try:
        normalize_geography(conn, args.zoo_table)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
