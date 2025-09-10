#!/usr/bin/env python3
"""
Infer IUCN conservation status from German 'Gefährdungsstatus' JSON field.

- Only fills rows where iucn_conservation_status is NULL or empty.
- Uses exact string mapping (do not change formatting).
- Tries a single SQL UPDATE using JSON1; falls back to Python per-row updates
  if JSON1 functions are unavailable.

Usage:
  python infer_iucn_from_zootierliste.py path/to/db.sqlite \
      --table animals \
      --desc-col zootierliste_description \
      --iucn-col iucn_conservation_status
"""
import argparse, sqlite3, json

MAPPING = {
    "LC (nicht gefährdet)": "Least Concern",
    "VU (gefährdet)": "Vulnerable",
    "EN (stark gefährdet)": "Endangered status",
    "NT (gering gefährdet)": "Near Threatened",
    "CR (vom Aussterben bedroht)": "Critically Endangered",
    "DD (Daten unzureichend)": "Data Deficient",
    "EW (in freier Natur ausgestorben)": "extinct in the wild",
}

def try_sql_update(con, table, desc_col, iucn_col):
    """
    Fast path: single SQL UPDATE using JSON1.
    Returns number of rows updated, or raises OperationalError if JSON1 missing.
    """
    placeholders_g = ",".join(["?"] * len(MAPPING))
    # Build CASE WHEN ... THEN ... using parameters
    case_parts = []
    params = []
    for g, e in MAPPING.items():
        case_parts.append("WHEN TRIM(json_extract({dc}, '$.Gefährdungsstatus')) = ? THEN ?".format(dc=desc_col))
        params.extend([g, e])
    case_sql = " ".join(case_parts)

    sql = f"""
    UPDATE {table}
    SET {iucn_col} = CASE
        {case_sql}
        ELSE {iucn_col}
    END
    WHERE ({iucn_col} IS NULL OR TRIM({iucn_col}) = '')
      AND json_valid({desc_col})
      AND TRIM(json_extract({desc_col}, '$.Gefährdungsstatus')) IN ({placeholders_g})
    """
    params.extend(list(MAPPING.keys()))
    cur = con.cursor()
    cur.execute(sql, params)
    con.commit()
    return cur.rowcount if cur.rowcount is not None else 0

def python_fallback_update(con, table, desc_col, iucn_col):
    """
    Safe fallback if JSON1 is unavailable: parse JSON in Python, row by row.
    """
    cur = con.cursor()
    cur.execute(f"""
        SELECT rowid, {desc_col}
        FROM {table}
        WHERE {iucn_col} IS NULL OR TRIM({iucn_col}) = ''
    """)
    rows = cur.fetchall()
    updates = []
    stats = {k: 0 for k in MAPPING.keys()}

    for rowid, desc_text in rows:
        if not isinstance(desc_text, str) or not desc_text.strip():
            continue
        try:
            data = json.loads(desc_text)
        except Exception:
            continue
        g = data.get("Gefährdungsstatus")
        if not g:
            continue
        g = str(g).strip()
        e = MAPPING.get(g)
        if e:
            updates.append((e, rowid))
            stats[g] += 1

    if updates:
        cur.executemany(f"UPDATE {table} SET {iucn_col} = ? WHERE rowid = ?", updates)
        con.commit()

    return sum(stats.values()), stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", help="Path to SQLite database")
    ap.add_argument("--table", default="animal", help="Table name (default: animal)")
    ap.add_argument("--desc-col", default="zootierliste_description",
                    help="JSON text column (default: zootierliste_description)")
    ap.add_argument("--iucn-col", default="iucn_conservation_status",
                    help="IUCN status column (default: iucn_conservation_status)")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)

    # First try the fast JSON1 UPDATE; if JSON1 is missing, fall back.
    try:
        updated = try_sql_update(con, args.table, args.desc_col, args.iucn_col)
        print(f"Updated rows (JSON1 fast path): {updated}")
    except sqlite3.OperationalError as e:
        # Likely: "no such function: json_extract" or similar
        print(f"JSON1 not available ({e}); using Python fallback…")
        updated, per_key = python_fallback_update(con, args.table, args.desc_col, args.iucn_col)
        print(f"Updated rows (Python fallback): {updated}")
        if updated:
            print("Breakdown by 'Gefährdungsstatus':")
            for g, cnt in per_key.items():
                if cnt:
                    print(f"  {g}  →  {MAPPING[g]} : {cnt}")

    con.close()

if __name__ == "__main__":
    main()

