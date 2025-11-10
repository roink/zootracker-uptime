#!/usr/bin/env python3
"""
fix_apostrophes_unify.py

Unify apostrophes used for English possessives in an SQLite table column:
- Normalize any apostrophe-like character to U+2019 (’).
- Fix these patterns:
  1) <apostrophe> + 's' + (space|punct|end)  -> ’s (space/punct preserved)
  2) 's' + <apostrophe> + (space|punct|end)  -> s’ (space/punct preserved)
  3) 's' + <apostrophe> + <LETTER>          -> s’ <LETTER>   (inserts a space)
     e.g., 'Griffis`angelfish' -> 'Griffis’ angelfish'

It is conservative: it does NOT touch names like O'Connor (letter ' letter).

Usage:
  python fix_apostrophes_unify.py --db zootracker.sqlite --table animal --pk id --col name_en --dry-run
  python fix_apostrophes_unify.py --db zootracker.sqlite --table animal --pk id --col name_en
"""

import argparse
import re
import sqlite3
from typing import List, Tuple

# Apostrophe-like marks we normalize (includes the correct ’ so we can also fix spacing around it)
APOS = "`´‘’ʼ＇'"

# Precompile patterns (ordered for safe, idempotent passes)
# 1) Wrong/variant apostrophe before 's' when NOT followed by a letter: → ’s (keep following char)
PAT_S_POSSESSIVE_BOUNDARY = re.compile(rf"[{re.escape(APOS)}]s(?![A-Za-z])")

# 2) Wrong/variant apostrophe AFTER 's' when NOT followed by a letter: plural possessive → s’ (keep following char)
PAT_PLURAL_POSSESSIVE_BOUNDARY = re.compile(rf"s[{re.escape(APOS)}](?![A-Za-z])")

# 3) 's' + apostrophe + LETTER (no space) → s’ <LETTER>  (insert a single space)
#    Example: Griffis`angelfish -> Griffis’ angelfish
PAT_MISSING_SPACE_AFTER_POSSESSIVE = re.compile(rf"([sS])[{re.escape(APOS)}](?=[A-Za-z])")

# 4) Variant apostrophe before 's' + whitespace (normalize the mark, keep whitespace)
PAT_S_POSSESSIVE_SPACE = re.compile(rf"[{re.escape(APOS)}]s(\s)")

# 5) 's' + variant apostrophe + whitespace (normalize the mark, keep whitespace)
PAT_PLURAL_POSSESSIVE_SPACE = re.compile(rf"s[{re.escape(APOS)}](\s)")

CORRECT = "’"  # U+2019 RIGHT SINGLE QUOTATION MARK

def needs_check(s: str) -> bool:
    """Heuristic: only scan rows that contain any apostrophe-like mark from APOS."""
    return any(ch in s for ch in APOS)

def fix_text(s: str) -> str:
    """
    Apply a few carefully ordered, idempotent rewrites to unify possessive apostrophes.
    """
    if not s:
        return s

    orig = s

    # 3) s + apostrophe + LETTER -> s’ <LETTER>
    s = PAT_MISSING_SPACE_AFTER_POSSESSIVE.sub(r"\1’ ", s)

    # 4) apostrophe + 's' + space -> ’s <space>
    s = PAT_S_POSSESSIVE_SPACE.sub(r"’s\1", s)

    # 1) apostrophe + 's' + boundary (EOS or non-letter) -> ’s
    s = PAT_S_POSSESSIVE_BOUNDARY.sub("’s", s)

    # 5) 's' + apostrophe + space -> s’ <space>
    s = PAT_PLURAL_POSSESSIVE_SPACE.sub(r"s’\1", s)

    # 2) 's' + apostrophe + boundary -> s’
    s = PAT_PLURAL_POSSESSIVE_BOUNDARY.sub("s’", s)

    return s if s != orig else orig

def fetch_candidates(conn: sqlite3.Connection, table: str, pk: str, col: str) -> List[Tuple[str, str]]:
    # Narrow to rows containing any apostrophe-like character (cheap LIKEs)
    likes = " OR ".join([f'"{col}" LIKE ?' for _ in APOS])
    params = [f"%{ch}%" for ch in APOS]
    sql = f'SELECT "{pk}", "{col}" FROM "{table}" WHERE {likes}'
    return [(str(row[0]), row[1] or "") for row in conn.execute(sql, params)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--table", default="animal")
    ap.add_argument("--pk", default="art")
    ap.add_argument("--col", default="name_en")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Connect
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        # Basic existence checks
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (args.table,)).fetchone():
            raise SystemExit(f'Table "{args.table}" not found.')
        cols = {r["name"] for r in conn.execute(f'PRAGMA table_info("{args.table}")')}
        if args.pk not in cols or args.col not in cols:
            missing = [c for c in (args.pk, args.col) if c not in cols]
            raise SystemExit(f'Missing column(s) in "{args.table}": {", ".join(missing)}')

        rows = fetch_candidates(conn, args.table, args.pk, args.col)

        updates: List[Tuple[str, str]] = []
        for rid, text in rows:
            if not needs_check(text):
                continue
            fixed = fix_text(text)
            if fixed != text:
                updates.append((fixed, rid))

        if not updates:
            print("No replacements needed.")
            return

        print(f"Will update {len(updates)} row(s). Examples:")
        for fixed, rid in updates[:20]:
            # show before/after
            before = next(v for v in rows if v[0] == rid)[1]
            print(f"  {rid}: {before!r}  ->  {fixed!r}")
        if len(updates) > 20:
            print(f"  ... and {len(updates) - 20} more")

        if args.dry_run:
            print("\n[DRY-RUN] No changes written.")
            return

        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            f'UPDATE "{args.table}" SET "{args.col}" = ? WHERE "{args.pk}" = ?',
            updates,
        )
        changed = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        print(f"Updated {changed} row(s).")
    finally:
        conn.close()

if __name__ == "__main__":
    main()

