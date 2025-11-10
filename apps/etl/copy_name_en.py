#!/usr/bin/env python3
"""
Copy English names (name_en) from a *source* SQLite DB to a *target* SQLite DB.

- Both DBs must contain an `animal` table with primary key `art`.
- Values are matched by `art`.
- By default, updates happen only when the incoming value differs from the
  current target value (whitespace-insensitive). Use --only-missing to update
  only rows where the target has NULL/empty `name_en`.
- If `name_en` is missing in the target, it will be created (TEXT column).

Usage:
  python copy_name_en.py --source SRC.db --target TGT.db [--only-missing] [--dry-run] [--backup]

Examples:
  # Update missing and differing values, commit changes
  python copy_name_en.py -s src.db -t tgt.db

  # Only fill blanks (do not overwrite existing non-empty values)
  python copy_name_en.py -s src.db -t tgt.db --only-missing

  # Preview what would change, without writing
  python copy_name_en.py -s src.db -t tgt.db --dry-run

  # Make a timestamped backup of the target DB before writing
  python copy_name_en.py -s src.db -t tgt.db --backup
"""

from __future__ import annotations
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from typing import List, Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", "-s", required=True, help="Path to source SQLite DB (has authoritative name_en)")
    p.add_argument("--target", "-t", required=True, help="Path to target SQLite DB (will be updated)")
    p.add_argument("--only-missing", action="store_true", help="Only fill when target name_en is NULL/empty; do not overwrite non-empty")
    p.add_argument("--dry-run", action="store_true", help="Show what would change; do not write any changes")
    p.add_argument("--backup", action="store_true", help="Create a timestamped copy of the target DB before modifying")
    return p.parse_args()


def ensure_table_and_columns(conn: sqlite3.Connection, db_path: str, *, create_target_name_en: bool) -> None:
    def has_column(table: str, col: str) -> bool:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == col for row in cur.fetchall())

    # Basic checks
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='animal'")
    if cur.fetchone() is None:
        sys.exit(f"ERROR: {db_path}: table 'animal' not found")

    # 'art' must exist
    if not has_column("animal", "art"):
        sys.exit(f"ERROR: {db_path}: table 'animal' lacks required column 'art'")

    # Ensure name_en exists (create if requested)
    if not has_column("animal", "name_en"):
        if create_target_name_en:
            conn.execute("ALTER TABLE animal ADD COLUMN name_en TEXT")
            conn.commit()
            print(f"{os.path.basename(db_path)}: Added missing column 'name_en' to table 'animal'.")
        else:
            sys.exit(f"ERROR: {db_path}: table 'animal' lacks column 'name_en'")


def load_source_values(src: sqlite3.Connection) -> List[Tuple[str, str]]:
    # Fetch art + name_en where name_en is not null/empty after TRIM
    rows = src.execute(
        """
        SELECT art, name_en
        FROM animal
        WHERE name_en IS NOT NULL AND TRIM(name_en) <> ''
        """
    ).fetchall()
    # Normalize whitespace (trim) in-memory to avoid churn on trivial diffs
    return [(str(art), name.strip()) for art, name in rows]


def load_target_keys(tgt: sqlite3.Connection) -> set:
    return {str(row[0]) for row in tgt.execute("SELECT art FROM animal")}


def preview_examples(updates: List[Tuple[str, str]], limit: int = 10) -> None:
    if not updates:
        print("No candidate updates found.")
        return
    print("Examples (art -> name_en):")
    for art, name in updates[:limit]:
        print(f"  {art!r} -> {name!r}")
    if len(updates) > limit:
        print(f"  ... and {len(updates) - limit} more")


def main() -> None:
    args = parse_args()

    if not os.path.exists(args.source):
        sys.exit(f"ERROR: Source DB not found: {args.source}")
    if not os.path.exists(args.target):
        sys.exit(f"ERROR: Target DB not found: {args.target}")

    if args.backup and not args.dry_run:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        base, ext = os.path.splitext(args.target)
        backup_path = f"{base}.backup-{ts}{ext or '.db'}"
        shutil.copy2(args.target, backup_path)
        print(f"Backup created: {backup_path}")

    with sqlite3.connect(args.source) as src_conn, sqlite3.connect(args.target) as tgt_conn:
        src_conn.row_factory = sqlite3.Row
        tgt_conn.row_factory = sqlite3.Row

        # Checks
        ensure_table_and_columns(src_conn, args.source, create_target_name_en=False)
        ensure_table_and_columns(tgt_conn, args.target, create_target_name_en=True)

        # Load data
        src_values = load_source_values(src_conn)  # list of (art, name_en)
        tgt_keys = load_target_keys(tgt_conn)

        total_from_source = len(src_values)
        candidates = [(art, name) for art, name in src_values if art in tgt_keys]
        unmatched = total_from_source - len(candidates)

        # Build update statement
        if args.only_missing:
            # Update only where target is NULL or empty (after TRIM)
            sql = (
                "UPDATE animal SET name_en = ? "
                "WHERE art = ? AND (name_en IS NULL OR TRIM(name_en) = '')"
            )
            params = [(name, art) for art, name in candidates]
        else:
            # Update when different (whitespace-insensitive)
            sql = (
                "UPDATE animal SET name_en = ? "
                "WHERE art = ? AND (name_en IS NULL OR TRIM(name_en) <> TRIM(?))"
            )
            params = [(name, art, name) for art, name in candidates]

        # Dry-run: estimate affected rows by probing a sample (optional)
        print(f"Source rows with non-empty name_en: {total_from_source}")
        print(f"Candidates with matching art in target: {len(candidates)}")
        print(f"Unmatched art values (absent in target): {unmatched}")
        preview_examples(candidates)

        if args.dry_run or not candidates:
            print("Dry run: no changes written.")
            return

        # Execute updates in a single transaction
        before = tgt_conn.total_changes
        tgt_conn.execute("BEGIN")
        try:
            tgt_conn.executemany(sql, params)
            tgt_conn.commit()
        except Exception:
            tgt_conn.rollback()
            raise
        after = tgt_conn.total_changes
        updated = after - before

        print(f"Rows updated in target: {updated}")
        if args.only_missing:
            print("Mode: only-missing (did not overwrite existing non-empty values)")
        else:
            print("Mode: overwrite-if-different (trim-insensitive comparison)")


if __name__ == "__main__":
    main()

