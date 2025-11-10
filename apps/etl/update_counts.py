#!/usr/bin/env python3
"""Recalculate zoo and species counts in the SQLite database."""
import argparse
import sqlite3

from zootier_scraper_sqlite import DB_FILE, ensure_db_schema, update_counts

def main():
    parser = argparse.ArgumentParser(description="Populate count columns for animals and zoos")
    parser.add_argument("--db", default=DB_FILE, help="Path to SQLite database file")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    ensure_db_schema(conn)
    with conn:
        update_counts(conn)
    cur = conn.cursor()
    animals = cur.execute("SELECT COUNT(*) FROM animal").fetchone()[0]
    zoos = cur.execute("SELECT COUNT(*) FROM zoo").fetchone()[0]
    conn.close()
    print(f"Updated counts for {animals} animals and {zoos} zoos")

if __name__ == "__main__":
    main()
