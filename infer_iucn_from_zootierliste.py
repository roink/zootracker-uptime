#!/usr/bin/env python3
import argparse, sqlite3, json, re, sys

CODE_RE = re.compile(r"^\s*([A-Z]{2,3})(?:\b|-)")  # grabs LC, NT, VU, EN, CR, DD, NE, EW, EX, GEH-*

# Map strictly to existing strings in your DB (exact casing/spelling)
IUCN_MAP = {
    "LC": "Least Concern",
    "NT": "Near Threatened",
    "VU": "Vulnerable",
    "EN": "Endangered status",      # note: unusual label, but matches your DB
    "CR": "Critically Endangered",
    "DD": "Data Deficient",
    "EW": "extinct in the wild",
    "EX": "extinct species",
    # "NE":  (Not Evaluated) -> intentionally skipped to avoid introducing new value
}

SKIP_CODES = {"NE", "GEH"}  # NE (Not Evaluated) + German Red List buckets (GEH-*)

def find_primary_key(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    cols = cur.fetchall()
    # cols: cid, name, type, notnull, dflt_value, pk
    for _cid, name, _type, _notnull, _dflt, pk in cols:
        if pk:  # first column with pk flag
            return name
    # Fallback to rowid if no explicit PK (works unless table was created WITHOUT ROWID)
    return "rowid"

def main():
    ap = argparse.ArgumentParser(description="Fill missing IUCN statuses from German 'Gefährdungsstatus' JSON.")
    ap.add_argument("db", help="Path to SQLite database")
    ap.add_argument("--table", default="animal", help="Table name (default: animal)")
    ap.add_argument("--desc-col", default="zootierliste_description",
                    help="JSON text column (default: zootierliste_description)")
    ap.add_argument("--iucn-col", default="iucn_conservation_status",
                    help="IUCN status column (default: iucn_conservation_status)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()
    pk_col = find_primary_key(cur, args.table)

    # Select only rows where the IUCN column is NULL or empty/whitespace
    cur.execute(f"""
        SELECT {pk_col}, {args.desc_col}
        FROM {args.table}
        WHERE {args.iucn_col} IS NULL OR TRIM({args.iucn_col}) = ''
    """)

    to_update = []
    skipped_ne_or_geh = 0
    skipped_no_match = 0
    malformed_json = 0

    for pk, desc_text in cur.fetchall():
        if not isinstance(desc_text, str) or not desc_text.strip():
            skipped_no_match += 1
            continue
        try:
            data = json.loads(desc_text)
        except Exception:
            malformed_json += 1
            continue

        g = data.get("Gefährdungsstatus")
        if not g or not isinstance(g, str):
            skipped_no_match += 1
            continue

        m = CODE_RE.match(g)
        if not m:
            skipped_no_match += 1
            continue

        code = m.group(1)
        # Normalize GEH-* to GEH
        if code.startswith("GEH"):
            code = "GEH"

        if code in SKIP_CODES:
            skipped_ne_or_geh += 1
            continue

        mapped = IUCN_MAP.get(code)
        if mapped:
            to_update.append((mapped, pk))
        else:
            # Unknown/unsupported code — skip
            skipped_no_match += 1

    print(f"Rows to update: {len(to_update)}")
    print(f"Skipped NE/GEH: {skipped_ne_or_geh}")
    print(f"Skipped (no/unknown match): {skipped_no_match}")
    print(f"Malformed JSON: {malformed_json}")

    if not args.dry_run and to_update:
        cur.executemany(
            f"UPDATE {args.table} SET {args.iucn_col} = ? WHERE {pk_col} = ?",
            to_update
        )
        con.commit()
        print(f"Updated {cur.rowcount} rows.")
    elif args.dry_run:
        print("Dry-run mode: no changes written.")

    con.close()

if __name__ == "__main__":
    main()

