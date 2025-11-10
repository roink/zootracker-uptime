#!/usr/bin/env python3
"""
copy_zoo_metadata.py  — normalized key matching

Copy these columns from source.zoo -> target.zoo when there's a 1:1 match on
(country, city, name):

  description_en, description_de, official_website, wikipedia_en, wikipedia_de

Matching defaults:
  - Normalize whitespace (replace NBSP etc. with normal space, collapse runs)
  - Case-sensitive (use --case-insensitive to change)
  - Keep 1:1 uniqueness AFTER normalization in BOTH DBs

Behavior:
  - Adds missing target columns as TEXT if needed
  - Fills only NULL/"" unless --overwrite
  - Use --dry-run to preview

Usage:
  python copy_zoo_metadata.py src.db dst.db
  python copy_zoo_metadata.py src.db dst.db --overwrite --verbose
  python copy_zoo_metadata.py src.db dst.db --case-insensitive
  python copy_zoo_metadata.py src.db dst.db --exact-match   # disables normalization
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from typing import Dict, Tuple, List, Optional

COLUMNS = [
    "description_en",
    "description_de",
    "official_website",
    "wikipedia_en",
    "wikipedia_de",
]
KEY_COLS = ["country", "city", "name"]


# ------------------------- normalization helpers -------------------------

def _norm_part(s: Optional[str], casefold: bool) -> Optional[str]:
    if s is None:
        return None
    # Unicode normalize first
    s = unicodedata.normalize("NFKC", s)
    # Replace common "non-space spaces" with a normal space
    s = s.replace("\u00A0", " ").replace("\u202F", " ").replace("\u2007", " ")
    # Collapse any whitespace (keeps ordinary spaces)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
    return s.casefold() if casefold else s

def normalize_key(key: Tuple[str, str, str], do_normalize: bool, casefold: bool) -> Tuple[str, str, str]:
    country, city, name = key
    if not do_normalize:
        return (country if not casefold else country.casefold(),
                city if not casefold else city.casefold(),
                name if not casefold else name.casefold())
    return (
        _norm_part(country, casefold),
        _norm_part(city, casefold),
        _norm_part(name, casefold),
    )

def is_valid_normkey(k: Tuple[Optional[str], Optional[str], Optional[str]]) -> bool:
    # skip if any piece is None or empty after normalization
    return all(part is not None and part != "" for part in k)


# ------------------------- schema + utilities -------------------------

def get_existing_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return [row[1] for row in cur.fetchall()]

def ensure_target_columns(conn: sqlite3.Connection, table: str, needed: List[str], verbose: bool=False):
    existing = set(get_existing_columns(conn, table))
    for col in needed:
        if col not in existing:
            if verbose:
                print(f'Adding missing column "{col}" to {table}...')
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT')


# ------------------------- indexing with normalization -------------------------

def build_source_index(
    conn: sqlite3.Connection,
    table: str,
    do_normalize: bool,
    casefold: bool,
) -> Dict[Tuple[str, str, str], Tuple[Tuple[str, str, str], Tuple]]:
    """
    Returns dict:
      norm_key -> (exact_key, values_tuple_for_COLUMNS)
    Only includes norm_keys that are UNIQUE (count==1) after normalization.
    """
    select_cols = ", ".join([*KEY_COLS, *COLUMNS])
    cur = conn.execute(f'SELECT {select_cols} FROM "{table}" WHERE country IS NOT NULL AND city IS NOT NULL AND name IS NOT NULL')
    counts: Dict[Tuple[str, str, str], int] = {}
    last: Dict[Tuple[str, str, str], Tuple[Tuple[str, str, str], Tuple]] = {}

    for row in cur.fetchall():
        exact_key = (row[0], row[1], row[2])
        vals = tuple(row[3:3+len(COLUMNS)])
        nkey = normalize_key(exact_key, do_normalize, casefold)
        if not is_valid_normkey(nkey):
            continue
        counts[nkey] = counts.get(nkey, 0) + 1
        last[nkey] = (exact_key, vals)

    # keep only uniques
    return {k: v for k, v in last.items() if counts.get(k) == 1}


def build_target_index(
    conn: sqlite3.Connection,
    table: str,
    do_normalize: bool,
    casefold: bool,
) -> Dict[Tuple[str, str, str], Tuple[str, str, str]]:
    """
    Returns dict:
      norm_key -> exact_key
    Only includes norm_keys that are UNIQUE (count==1) after normalization.
    """
    cur = conn.execute(f'SELECT country, city, name FROM "{table}" WHERE country IS NOT NULL AND city IS NOT NULL AND name IS NOT NULL')
    counts: Dict[Tuple[str, str, str], int] = {}
    last: Dict[Tuple[str, str, str], Tuple[str, str, str]] = {}

    for row in cur.fetchall():
        exact_key = (row[0], row[1], row[2])
        nkey = normalize_key(exact_key, do_normalize, casefold)
        if not is_valid_normkey(nkey):
            continue
        counts[nkey] = counts.get(nkey, 0) + 1
        last[nkey] = exact_key

    return {k: v for k, v in last.items() if counts.get(k) == 1}


# ------------------------- main copy logic -------------------------

def main():
    ap = argparse.ArgumentParser(description="Copy zoo metadata between SQLite DBs by (country, city, name) with normalization.")
    ap.add_argument("source_db")
    ap.add_argument("target_db")
    ap.add_argument("--source-table", default="zoo")
    ap.add_argument("--target-table", default="zoo")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite non-empty values in target")
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--exact-match", action="store_true", help="Disable normalization (use exact strings)")
    ap.add_argument("--case-insensitive", action="store_true", help="Case-insensitive matching (applies to normalized or exact)")
    args = ap.parse_args()

    src = sqlite3.connect(args.source_db)
    dst = sqlite3.connect(args.target_db)

    try:
        src.row_factory = sqlite3.Row
        dst.row_factory = sqlite3.Row

        # Sanity: source has required columns
        src_cols = set(get_existing_columns(src, args.source_table))
        missing_in_source = [c for c in [*KEY_COLS, *COLUMNS] if c not in src_cols]
        if missing_in_source:
            raise SystemExit(f"Source table '{args.source_table}' missing columns: {missing_in_source}")

        ensure_target_columns(dst, args.target_table, COLUMNS, verbose=args.verbose)

        do_normalize = not args.exact_match
        casefold = args.case_insensitive

        if args.verbose:
            print(f"Matching with: normalize_whitespace={do_normalize}, case_insensitive={casefold}")

        src_index = build_source_index(src, args.source_table, do_normalize, casefold)
        dst_index = build_target_index(dst, args.target_table, do_normalize, casefold)

        # Intersection on normalized keys
        inter_keys = [k for k in src_index.keys() if k in dst_index]
        if args.verbose:
            print(f"Unique normalized keys — source: {len(src_index)}, target: {len(dst_index)}, intersection: {len(inter_keys)}")

        # Prepare SQL
        set_parts_overwrite = ", ".join([f'"{col}" = ?' for col in COLUMNS])
        set_parts_fill = ", ".join([
            f'"{col}" = CASE WHEN "{col}" IS NULL OR "{col}" = "" THEN ? ELSE "{col}" END'
            for col in COLUMNS
        ])

        # Plan updates
        planned_updates = []
        skipped_already_filled = 0

        sel_target = f'''
            SELECT {", ".join(COLUMNS)}
            FROM "{args.target_table}"
            WHERE country = ? AND city = ? AND name = ?
        '''

        for nkey in inter_keys:
            (src_exact_key, src_vals) = src_index[nkey]
            tgt_exact_key = dst_index[nkey]

            if not args.overwrite:
                cur = dst.execute(sel_target, tgt_exact_key)
                row = cur.fetchone()
                if row:
                    all_filled = True
                    for col in COLUMNS:
                        val = row[col]
                        if val is None or val == "":
                            all_filled = False
                            break
                    if all_filled:
                        skipped_already_filled += 1
                        continue

            planned_updates.append((tgt_exact_key, src_vals))

        if args.verbose:
            print(f"Planned updates: {len(planned_updates)} (skipped already-filled: {skipped_already_filled})")

        if args.dry_run:
            print(f"[DRY RUN] Would update {len(planned_updates)} rows in target.")
            return

        # Execute updates
        with dst:
            upd_sql = f'''
                UPDATE "{args.target_table}"
                SET {set_parts_overwrite if args.overwrite else set_parts_fill}
                WHERE country = ? AND city = ? AND name = ?
            '''
            params_batch = []
            for (tgt_exact_key, src_vals) in planned_updates:
                params_batch.append((*src_vals, *tgt_exact_key))
            dst.executemany(upd_sql, params_batch)

        print(f"Done. Updated rows: {dst.total_changes}. Skipped already-filled: {skipped_already_filled}. Considered: {len(inter_keys)}.")

    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()

