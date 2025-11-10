#!/usr/bin/env python3
"""Copy continent info between SQLite databases based on country.

This script fills the ``continent`` column in the target database's ``zoo``
table by looking up a matching ``country`` in the source database's ``zoo``
table and copying the corresponding ``continent`` value.

Usage:
    python copy_continent_from_country.py source.db target.db

The script only updates rows where ``continent`` is ``NULL`` or empty in the
target database. Use ``--overwrite`` to replace existing values.
"""

from __future__ import annotations

import argparse
import sqlite3

from copy_zoo_metadata import ensure_target_columns, get_existing_columns


def build_country_continent_map(
    conn: sqlite3.Connection, table: str
) -> dict[str, str]:
    """Return a mapping of country -> continent from ``table``.

    Only rows with non-empty ``country`` and ``continent`` are included. The
    first occurrence of a country is used if duplicates exist.
    """

    mapping: dict[str, str] = {}
    cur = conn.execute(
        f"SELECT country, continent FROM \"{table}\" WHERE continent IS NOT NULL"
    )
    for country, continent in cur.fetchall():
        if not country or not continent:
            continue
        mapping.setdefault(country, continent)
    return mapping


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Fill the 'continent' column in the target DB's zoo table using "
            "matching 'country' values from the source DB."
        )
    )
    ap.add_argument("source_db")
    ap.add_argument("target_db")
    ap.add_argument("--source-table", default="zoo")
    ap.add_argument("--target-table", default="zoo")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing continent values in the target table",
    )
    args = ap.parse_args()

    src = sqlite3.connect(args.source_db)
    dst = sqlite3.connect(args.target_db)

    try:
        src.row_factory = sqlite3.Row
        dst.row_factory = sqlite3.Row

        # Ensure required columns exist
        src_cols = set(get_existing_columns(src, args.source_table))
        for col in ["country", "continent"]:
            if col not in src_cols:
                raise SystemExit(
                    f"Source table '{args.source_table}' missing column '{col}'"
                )

        ensure_target_columns(dst, args.target_table, ["continent"])

        mapping = build_country_continent_map(src, args.source_table)

        # Fetch rows from target and plan updates
        cur = dst.execute(
            f"SELECT rowid, country, continent FROM \"{args.target_table}\""
        )
        updates: list[tuple[str, int]] = []
        for rowid, country, existing in cur.fetchall():
            if not country:
                continue
            continent = mapping.get(country)
            if not continent:
                continue
            if not args.overwrite and existing not in (None, ""):
                continue
            updates.append((continent, rowid))

        if updates:
            with dst:
                dst.executemany(
                    f"UPDATE \"{args.target_table}\" SET continent = ? WHERE rowid = ?",
                    updates,
                )

        print(f"Updated rows: {dst.total_changes}")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
