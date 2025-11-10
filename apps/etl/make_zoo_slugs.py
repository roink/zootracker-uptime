#!/usr/bin/env python3
"""
make_zoo_slugs.py — Create unique URL slugs for zoos from (city + " " + name).

Rules & behavior:
- Source text is computed in memory as:
    label = (city + " " + name) if both present, else (city or name)
- Slug normalization, apostrophe stripping, ASCII folding, and uniqueness
  are reused from make_slugs.py.
- Order of assignment: order_col DESC, label ASC, pk ASC
- If label becomes empty after cleaning, fallback to 'unnamed-<pk>'.

Usage examples:
  python make_zoo_slugs.py --db app.sqlite
  python make_zoo_slugs.py --db app.sqlite --table zoo --pk zoo_id \
      --city-col city --name-col name --order-col species_count
  python make_zoo_slugs.py --db app.sqlite --dry-run
  python make_zoo_slugs.py --db app.sqlite --reset
"""

from __future__ import annotations

import argparse
import sqlite3
from typing import List, Tuple, Optional

# Reuse helpers from your existing script
from make_slugs import (
    validate_identifier,
    table_exists,
    column_exists,
    ensure_column,
    ensure_unique_index,
    fetch_existing_slugs,
    compute_slug_assignments,
    apply_updates,
)

def rows_to_fill_concat(
    conn: sqlite3.Connection,
    table: str,
    pk: str,
    slug_col: str,
    city_col: str,
    name_col: str,
    order_col: str,
    reset: bool,
) -> List[Tuple[str, str]]:
    """
    Return [(pk, label)] where label = city + ' ' + name (if both present),
    else just city or name. Only rows with empty slug unless --reset.
    Ordered by order_col DESC, label ASC, pk ASC.
    """
    where = "" if reset else f'WHERE ("{slug_col}" IS NULL OR "{slug_col}" = "")'

    # Build label in SELECT without writing anything to the DB.
    # Only insert a space if both parts are non-empty.
    label_expr = (
        f'CASE '
        f'  WHEN COALESCE("{city_col}", "") <> "" AND COALESCE("{name_col}", "") <> "" '
        f'    THEN "{city_col}" || " " || "{name_col}" '
        f'  ELSE COALESCE("{city_col}", "") || COALESCE("{name_col}", "") '
        f'END AS label'
    )

    sql = (
        f'SELECT "{pk}", {label_expr} '
        f'FROM "{table}" '
        f'{where} '
        f'ORDER BY "{order_col}" DESC, label ASC, "{pk}" ASC'
    )
    cur = conn.execute(sql)
    return [(str(row[0]), row[1] if row[1] is not None else "") for row in cur.fetchall()]


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Create unique slugs for zoos from (city + name).")
    ap.add_argument("--db", required=True, help="Path to SQLite database")
    ap.add_argument("--table", default="zoo", help='Zoo table name (default: "zoo")')
    ap.add_argument("--pk", default="zoo_id", help='Primary key column (default: "zoo_id")')
    ap.add_argument("--city-col", default="city", help='City column (default: "city")')
    ap.add_argument("--name-col", default="name", help='Zoo name column (default: "name")')
    ap.add_argument("--slug-col", default="slug", help='Slug column to create/fill (default: "slug")')
    ap.add_argument("--order-col", default="species_count", help='Order column (default: "species_count")')
    ap.add_argument("--index-name", default=None, help="Custom unique index name (default: uniq_<table>_<slug_col>)")
    ap.add_argument("--reset", action="store_true", help="Recompute all slugs (ignore existing values)")
    ap.add_argument("--dry-run", action="store_true", help="Print planned changes without writing")
    args = ap.parse_args(argv)

    # Validate identifiers to avoid SQL injection through names
    table = validate_identifier("table", args.table)
    pk = validate_identifier("pk", args.pk)
    city_col = validate_identifier("city-col", args.city_col)
    name_col = validate_identifier("name-col", args.name_col)
    slug_col = validate_identifier("slug-col", args.slug_col)
    order_col = validate_identifier("order-col", args.order_col)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")

        if not table_exists(conn, table):
            raise SystemExit(f'Table "{table}" does not exist in {args.db}')

        # Ensure referenced columns exist
        for col in (pk, city_col, name_col, order_col):
            if not column_exists(conn, table, col):
                raise SystemExit(f'Column "{col}" not found in table "{table}"')

        if not args.dry_run:
            conn.execute("BEGIN IMMEDIATE")

        # Ensure slug column exists (added as TEXT if missing)
        ensure_column(conn, table, slug_col)

        # Select targets in desired order
        targets = rows_to_fill_concat(
            conn, table, pk, slug_col, city_col, name_col, order_col, args.reset
        )

        # Existing slugs (to avoid collisions), unless we're resetting all
        existing = [] if args.reset else fetch_existing_slugs(conn, table, slug_col)

        # Compute slug assignments using the shared uniqueness logic
        planned_updates = compute_slug_assignments(targets, existing)

        if args.dry_run:
            print(f"[DRY-RUN] {len(planned_updates)} rows would be updated.")
            for (slug, _pk) in planned_updates[:25]:
                print(f"  {_pk} -> {slug}")
            if len(planned_updates) > 25:
                print(f"  ... and {len(planned_updates) - 25} more")
            return

        # Apply updates
        changed = apply_updates(conn, table, pk, slug_col, planned_updates)

        # Enforce uniqueness at DB level
        ensure_unique_index(conn, table, slug_col, args.index_name)

        conn.commit()

        print(f"Updated rows: {changed}")
        print(f"Unique index ensured on {table}({slug_col}).")

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

