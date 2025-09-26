#!/usr/bin/env python3
"""
make_slugs.py — Add and populate a unique URL slug column in an SQLite table.

Slug rules:
- Build from `name_en` (configurable).
- Only lowercase `a`–`z` and `-`.
- Strip everything else; collapse consecutive '-' ; trim leading/trailing '-'.
- If empty after cleaning -> fallback to 'unnamed-<pk>'.
- Create in order of `zoo_count` DESC (configurable; tie-breakers: name_en ASC, pk ASC).
- Ensure uniqueness: first is 'name'; collisions become 'name-2', 'name-3', ...

Usage examples:
  python make_slugs.py --db app.sqlite --table zoo --pk zoo_id --src-col name_en --order-col zoo_count
  python make_slugs.py --db app.sqlite --table zoo --reset
  python make_slugs.py --db app.sqlite --table zoo --dry-run
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import unicodedata
from typing import Dict, Iterable, List, Optional, Set, Tuple


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")  # very conservative for identifiers
NON_AZ_RE = re.compile(r"[^a-z]+")
DASHES_RE = re.compile(r"-{2,}")
SLUG_WITH_NUM_RE = re.compile(r"^(?P<base>[a-z]+(?:-[a-z]+)*)(?:-(?P<num>\d+))?$")

# Common apostrophe-like characters to strip before normalization.
# - ASCII apostrophe: U+0027  '
# - Right/left single quotes (typographic apostrophes): U+2019, U+2018
# - Modifier letter apostrophe / primes / okina: U+02BC, U+02B9, U+02BB
# - Acute & grave accents sometimes used as apostrophes: U+00B4, U+0060
# - Fullwidth apostrophe: U+FF07
APOSTROPHE_CHARS = {
    "'", "’", "‘", "ʼ", "ʹ", "ʻ", "´", "`", "＇",
}
APOSTROPHE_TRANSLATION = dict.fromkeys(map(ord, APOSTROPHE_CHARS), None)

def strip_apostrophes(s: str) -> str:
    """Remove apostrophes and apostrophe-like marks before slug normalization."""
    if not s:
        return ""
    return s.translate(APOSTROPHE_TRANSLATION)



def validate_identifier(label: str, value: str) -> str:
    if not IDENT_RE.match(value):
        raise SystemExit(f"Invalid {label} identifier: {value!r}")
    return value


def norm_to_ascii_lower(s: str) -> str:
    """Unicode normalize + ASCII transliterate + lowercase."""
    if s is None:
        s = ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.lower()


def base_slug(name: str) -> str:
    """Convert an English name into a base slug (without numeric suffix)."""
    # First, strip all apostrophe variants so possessives collapse to plain 's'
    s = strip_apostrophes(name)
    s = norm_to_ascii_lower(s)
    s = NON_AZ_RE.sub("-", s)          # replace non a-z with '-'
    s = DASHES_RE.sub("-", s)          # collapse multiple '-'
    s = s.strip("-")                   # trim leading/trailing '-'
    return s


def parse_slug_existing(slug: str) -> Optional[Tuple[str, int]]:
    """
    Parse an existing slug into (base, n), where:
      - 'name'      -> ('name', 1)
      - 'name-2'    -> ('name', 2)
    Returns None if it doesn't look like a valid slug.
    """
    m = SLUG_WITH_NUM_RE.fullmatch(slug)
    if not m:
        return None
    base = m.group("base")
    num = m.group("num")
    return base, (int(num) if num is not None else 1)


def ensure_column(conn: sqlite3.Connection, table: str, slug_col: str) -> None:
    """Add slug column if missing (SQLite lacks IF NOT EXISTS for ADD COLUMN)."""
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    cols = [row[1] for row in cur.fetchall()]  # columns: cid, name, type, notnull, dflt_value, pk
    if slug_col not in cols:
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{slug_col}" TEXT')
        # Do not mark UNIQUE here; we create an index later.


def ensure_unique_index(conn: sqlite3.Connection, table: str, slug_col: str, index_name: Optional[str]) -> None:
    """Create a UNIQUE index to enforce one-of-a-kind slugs."""
    if not index_name:
        index_name = f"uniq_{table}_{slug_col}"
    conn.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}" ON "{table}"("{slug_col}")'
    )


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return any(row[1] == col for row in cur.fetchall())


def fetch_existing_slugs(conn: sqlite3.Connection, table: str, slug_col: str) -> List[str]:
    cur = conn.execute(
        f'SELECT "{slug_col}" FROM "{table}" WHERE "{slug_col}" IS NOT NULL AND "{slug_col}" <> ""'
    )
    return [r[0] for r in cur.fetchall() if r[0] is not None]


def rows_to_fill(
    conn: sqlite3.Connection,
    table: str,
    pk: str,
    src_col: str,
    slug_col: str,
    order_col: str,
    reset: bool,
) -> List[Tuple[str, str]]:
    """
    Return [(pk, name_en)] in required order.
    If not reset: only where slug is NULL or empty.
    """
    where = "" if reset else f'WHERE ("{slug_col}" IS NULL OR "{slug_col}" = "")'
    sql = (
        f'SELECT "{pk}", "{src_col}" '
        f'FROM "{table}" '
        f"{where} "
        f'ORDER BY "{order_col}" DESC, "{src_col}" ASC, "{pk}" ASC'
    )
    cur = conn.execute(sql)
    return [(str(row[0]), row[1] if row[1] is not None else "") for row in cur.fetchall()]


def compute_slug_assignments(
    targets: List[Tuple[str, str]],
    existing_slugs: Iterable[str],
) -> List[Tuple[str, str]]:
    """
    Given target rows (pk, name) and already-existing slugs, compute [(slug, pk)].
    Ensures uniqueness with numeric suffixes (-2, -3, ...) per base.
    """
    used: Set[str] = set()
    base_max: Dict[str, int] = {}

    # Seed with existing slugs in DB
    for sl in existing_slugs:
        parsed = parse_slug_existing(sl)
        if parsed is None:
            # Keep it reserved but don't try to infer a base/suffix
            used.add(sl)
            continue
        base, n = parsed
        used.add(sl)
        base_max[base] = max(base_max.get(base, 0), n)

    updates: List[Tuple[str, str]] = []

    for pk, name in targets:
        b = base_slug(name)
        if not b:
            b = f"unnamed-{pk}"

        # Determine next candidate number
        next_n = base_max.get(b, 0) + 1
        if next_n <= 1:
            candidate = b
        else:
            candidate = f"{b}-{next_n}"

        # Ensure global uniqueness
        while candidate in used:
            next_n += 1
            candidate = f"{b}-{next_n}"

        used.add(candidate)
        base_max[b] = next_n
        updates.append((candidate, pk))

    return updates


def apply_updates(
    conn: sqlite3.Connection,
    table: str,
    pk: str,
    slug_col: str,
    updates: List[Tuple[str, str]],
) -> int:
    if not updates:
        return 0
    conn.executemany(
        f'UPDATE "{table}" SET "{slug_col}" = ? WHERE "{pk}" = ?',
        updates,
    )
    return conn.total_changes


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Add and populate a unique slug column from name_en.")
    ap.add_argument("--db", required=True, help="Path to SQLite database")
    ap.add_argument("--table", default="animal", help="Table name (e.g., zoo)")
    ap.add_argument("--pk", default="art", help="Primary key column (default: id)")
    ap.add_argument("--src-col", default="name_en", help="Source name column (default: name_en)")
    ap.add_argument("--slug-col", default="slug", help="Slug column name to create/fill (default: slug)")
    ap.add_argument("--order-col", default="zoo_count", help="Order column for priority (default: zoo_count)")
    ap.add_argument("--index-name", default=None, help="Custom unique index name (default: uniq_<table>_<slug_col>)")
    ap.add_argument("--reset", action="store_true", help="Recompute all slugs (ignore existing values)")
    ap.add_argument("--dry-run", action="store_true", help="Print planned changes without writing")
    args = ap.parse_args(argv)

    # Validate identifiers (avoid accidental SQL injection through names)
    table = validate_identifier("table", args.table)
    pk = validate_identifier("pk", args.pk)
    src_col = validate_identifier("src-col", args.src_col)
    slug_col = validate_identifier("slug-col", args.slug_col)
    order_col = validate_identifier("order-col", args.order_col)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if not table_exists(conn, table):
            raise SystemExit(f'Table "{table}" does not exist in {args.db}')

        # Existence checks for referenced columns
        for col in (pk, src_col, order_col):
            if not column_exists(conn, table, col):
                raise SystemExit(f'Column "{col}" not found in table "{table}"')

        # Begin a transaction
        if not args.dry_run:
            conn.execute("BEGIN IMMEDIATE")

        # Ensure slug column exists
        ensure_column(conn, table, slug_col)

        # Select targets (ordered with required priority)
        targets = rows_to_fill(conn, table, pk, src_col, slug_col, order_col, args.reset)

        # Gather existing slugs to avoid collisions
        existing = [] if args.reset else fetch_existing_slugs(conn, table, slug_col)

        # Compute assignments
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

        # Create a UNIQUE index to enforce uniqueness at the DB level
        ensure_unique_index(conn, table, slug_col, args.index_name)

        conn.commit()

        print(f"Updated rows: {changed}")
        print(f"Unique index ensured on {table}({slug_col}).")

    except Exception as e:
        # Rollback on error if we started a write transaction
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

