#!/usr/bin/env python3
"""Populate the animal.parent_art column based on existing taxonomy data.

This script performs two passes to infer the species-level parent for
subspecies entries in the ``animal`` table.  It will add the ``parent_art``
column when missing and then fill it with the ``art`` identifier of the
species row that represents the parent taxon.

Strategy 1: use ``parent_taxon`` → ``wikidata_qid`` linkage when the class,
order, and family match.
Strategy 2: fall back to matching the first two parts of the normalized Latin
name (genus + species) among rows that share the same class/order/family.

Usage::

    python populate_parent_art.py --db path/to/zootracker.sqlite [--dry-run] [--log path.csv]

"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


@dataclass
class SubspeciesRow:
    art: str
    parent_taxon: Optional[str]
    klasse: Optional[str]
    ordnung: Optional[str]
    familie: Optional[str]
    normalized_latin_name: Optional[str]
    parent_art: Optional[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the SQLite database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without writing changes",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="Optional path to write CSV log for ambiguous/no-match rows",
    )
    return parser.parse_args()


def fetch_table_columns(conn: sqlite3.Connection, table: str) -> Sequence[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def ensure_parent_art_column(conn: sqlite3.Connection) -> bool:
    """Ensure the animal table has a parent_art column. Return True if added."""

    cols = fetch_table_columns(conn, "animal")
    if "parent_art" in cols:
        return False

    conn.execute(
        "ALTER TABLE animal ADD COLUMN parent_art TEXT REFERENCES animal(art)"
    )
    return True


def ensure_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_animal_qid_species
        ON animal(wikidata_qid)
        WHERE taxon_rank = 'species'
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_animal_scope_latin_species
        ON animal(klasse, ordnung, familie, normalized_latin_name)
        WHERE taxon_rank = 'species'
        """
    )


def load_subspecies(conn: sqlite3.Connection) -> list[SubspeciesRow]:
    rows = conn.execute(
        """
        SELECT art, parent_taxon, klasse, ordnung, familie,
               normalized_latin_name, parent_art
        FROM animal
        WHERE taxon_rank = 'subspecies'
        """
    ).fetchall()
    return [
        SubspeciesRow(
            art=str(row["art"]),
            parent_taxon=row["parent_taxon"],
            klasse=row["klasse"],
            ordnung=row["ordnung"],
            familie=row["familie"],
            normalized_latin_name=row["normalized_latin_name"],
            parent_art=row["parent_art"],
        )
        for row in rows
    ]


def coalesce(value: Optional[str]) -> str:
    return value or ""


def find_by_parent_taxon(
    conn: sqlite3.Connection, row: SubspeciesRow
) -> list[str]:
    if not row.parent_taxon:
        return []

    candidates = conn.execute(
        """
        SELECT art
        FROM animal
        WHERE wikidata_qid = ?
          AND taxon_rank = 'species'
          AND COALESCE(klasse, '') = ?
          AND COALESCE(ordnung, '') = ?
          AND COALESCE(familie, '') = ?
        """,
        ( 
            row.parent_taxon,
            coalesce(row.klasse),
            coalesce(row.ordnung),
            coalesce(row.familie),
        ),
    ).fetchall()

    return [str(candidate["art"]) for candidate in candidates]


def normalized_species_name(latin_name: Optional[str]) -> Optional[str]:
    if not latin_name:
        return None
    cleaned = latin_name.replace("×", " ")
    parts = cleaned.strip().split()
    if len(parts) < 2:
        return None
    return " ".join(parts[:2])


def preview_updates(updates: Sequence[tuple[str, str]], limit: int = 20) -> None:
    print("Sample updates (up to first {limit}):".format(limit=limit))
    for parent, child in updates[:limit]:
        print(f"  {child} ← {parent}")


def write_log(entries: Iterable[dict[str, str]], path: Path) -> None:
    if not entries:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["art", "strategy", "reason", "candidates"])
        writer.writeheader()
        writer.writerows(entries)


def find_by_latin_name(conn: sqlite3.Connection, row: SubspeciesRow) -> list[str]:
    species_name = normalized_species_name(row.normalized_latin_name)
    if not species_name:
        return []

    candidates = conn.execute(
        """
        SELECT art
        FROM animal
        WHERE normalized_latin_name = ?
          AND taxon_rank = 'species'
          AND COALESCE(klasse, '') = ?
          AND COALESCE(ordnung, '') = ?
          AND COALESCE(familie, '') = ?
        """,
        (
            species_name,
            coalesce(row.klasse),
            coalesce(row.ordnung),
            coalesce(row.familie),
        ),
    ).fetchall()

    return [str(candidate["art"]) for candidate in candidates]


def prepare_updates(
    conn: sqlite3.Connection, rows: Sequence[SubspeciesRow]
) -> tuple[list[tuple[str, str]], dict[str, int], list[dict[str, str]]]:
    updates: list[tuple[str, str]] = []
    stats = {
        "already_set": 0,
        "strategy_parent_taxon": 0,
        "strategy_latin_name": 0,
        "no_match": 0,
        "ambiguous_parent_taxon": 0,
        "ambiguous_latin_name": 0,
        "self_match": 0,
    }
    log_entries: list[dict[str, str]] = []

    for row in rows:
        if row.parent_art and row.parent_art.strip():
            stats["already_set"] += 1
            continue

        parent_candidates = find_by_parent_taxon(conn, row)
        if parent_candidates:
            if len(parent_candidates) == 1:
                parent = parent_candidates[0]
                if parent != row.art:
                    updates.append((parent, row.art))
                    stats["strategy_parent_taxon"] += 1
                    continue
                stats["self_match"] += 1
                log_entries.append(
                    {
                        "art": row.art,
                        "strategy": "parent_taxon",
                        "reason": "self_match",
                        "candidates": parent,
                    }
                )
            else:
                stats["ambiguous_parent_taxon"] += 1
                log_entries.append(
                    {
                        "art": row.art,
                        "strategy": "parent_taxon",
                        "reason": "ambiguous",
                        "candidates": "|".join(parent_candidates),
                    }
                )
            continue

        parent_candidates = find_by_latin_name(conn, row)
        if parent_candidates:
            if len(parent_candidates) == 1:
                parent = parent_candidates[0]
                if parent != row.art:
                    updates.append((parent, row.art))
                    stats["strategy_latin_name"] += 1
                    continue
                stats["self_match"] += 1
                log_entries.append(
                    {
                        "art": row.art,
                        "strategy": "latin_name",
                        "reason": "self_match",
                        "candidates": parent,
                    }
                )
            else:
                stats["ambiguous_latin_name"] += 1
                log_entries.append(
                    {
                        "art": row.art,
                        "strategy": "latin_name",
                        "reason": "ambiguous",
                        "candidates": "|".join(parent_candidates),
                    }
                )
            continue

        stats["no_match"] += 1
        log_entries.append(
            {
                "art": row.art,
                "strategy": "none",
                "reason": "no_match",
                "candidates": "",
            }
        )

    return updates, stats, log_entries


def main() -> None:
    args = parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Basic sanity check
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='animal'"
        ).fetchone()
        if not table_exists:
            raise SystemExit("Table 'animal' not found in the provided database")

        cols = fetch_table_columns(conn, "animal")
        parent_art_missing = "parent_art" not in cols
        if parent_art_missing:
            if args.dry_run:
                print("Column 'parent_art' missing; would add it (dry-run).")
            else:
                ensure_parent_art_column(conn)
                print("Added missing column 'parent_art' to table 'animal'.")

        if not args.dry_run:
            ensure_indexes(conn)
        else:
            print("Indexes would be created (dry-run).")

        subspecies_rows = load_subspecies(conn)
        print(f"Loaded {len(subspecies_rows)} subspecies rows.")

        updates, stats, log_entries = prepare_updates(conn, subspecies_rows)

        for key, value in stats.items():
            print(f"{key.replace('_', ' ').capitalize()}: {value}")

        if args.log:
            write_log(log_entries, args.log)
            print(f"Wrote log to {args.log}")

        if not updates:
            print("No updates required.")
            if not args.dry_run:
                conn.commit()
            return

        print(f"Prepared {len(updates)} update(s).")

        if args.dry_run:
            preview_updates(updates)
            print("Dry run requested; no changes written.")
            return

        conn.execute("BEGIN")
        try:
            conn.executemany(
                "UPDATE animal SET parent_art = ? WHERE art = ?",
                updates,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        print(f"Updated {len(updates)} row(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
