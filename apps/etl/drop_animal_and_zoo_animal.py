#!/usr/bin/env python3
# drop_animal_and_zoo_animal.py
import argparse
import datetime as dt
import os
import shutil
import sqlite3
import sys

def table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
        (name,),
    ).fetchone()
    return row is not None

def main():
    ap = argparse.ArgumentParser(description="Drop tables zoo_animal and animal from an SQLite DB.")
    ap.add_argument("--db", default="zootierliste.db", help="Path to SQLite database file")
    ap.add_argument("--yes", action="store_true", help="Confirm destructive action")
    ap.add_argument("--backup", action="store_true", help="Create a timestamped backup before dropping")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"[error] Database not found: {args.db}")
        sys.exit(2)

    if not args.yes:
        print("[abort] Refusing to drop tables without --yes")
        sys.exit(1)

    if args.backup:
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{args.db}.{ts}.bak"
        shutil.copy2(args.db, backup_path)
        print(f"[backup] {args.db} → {backup_path}")

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # Disable FK checks during schema changes, then drop child → parent
    cur.execute("PRAGMA foreign_keys = OFF;")

    dropped = []
    for tbl in ("zoo_animal", "animal"):
        if table_exists(cur, tbl):
            cur.execute(f"DROP TABLE {tbl};")
            dropped.append(tbl)
            print(f"[drop] {tbl}")
        else:
            print(f"[skip] {tbl} (does not exist)")

    conn.commit()
    cur.execute("PRAGMA foreign_keys = ON;")
    conn.close()

    print(f"[done] Dropped: {', '.join(dropped) if dropped else 'none'}")

if __name__ == "__main__":
    main()

