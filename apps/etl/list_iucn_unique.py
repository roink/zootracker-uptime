#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict

CODE_RE = re.compile(r"^\s*([A-Z]{1,3})\b")

def main():
    p = argparse.ArgumentParser(description="List unique IUCN + Gefährdungsstatus values")
    p.add_argument("db", help="Path to SQLite database")
    p.add_argument("--table", default="animal", help="Table name (default: animal)")
    p.add_argument("--desc-col", default="zootierliste_description",
                   help="JSON text column with German fields (default: zootierliste_description)")
    p.add_argument("--iucn-col", default="iucn_conservation_status",
                   help="IUCN status column (default: iucn_conservation_status)")
    args = p.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()

    cur.execute(f"""
        SELECT {args.desc_col}, {args.iucn_col}
        FROM {args.table}
    """)

    iucn_counter = Counter()
    g_status_counter = Counter()
    pair_counter = Counter()
    code_to_full = defaultdict(Counter)

    for desc_text, iucn in cur.fetchall():
        # IUCN status (English)
        iucn_clean = (iucn or "").strip()
        if iucn_clean == "":
            iucn_clean = None
        if iucn_clean is not None:
            iucn_counter[iucn_clean] += 1

        # Parse JSON text for "Gefährdungsstatus"
        g = None
        if isinstance(desc_text, str) and desc_text.strip():
            try:
                data = json.loads(desc_text)
                g = data.get("Gefährdungsstatus")
                if g is not None:
                    g = str(g).strip()
            except Exception:
                # ignore malformed JSON rows
                pass

        if g:
            g_status_counter[g] += 1
            # Extract short code like LC, NT, VU, EN, CR, DD, NE, EX, EW, etc.
            m = CODE_RE.match(g)
            code = m.group(1) if m else None
            if code:
                code_to_full[code][g] += 1

        if g and iucn_clean:
            pair_counter[(g, iucn_clean)] += 1

    # ---- Output ----
    print("Unique iucn_conservation_status values (with counts):")
    for val, cnt in iucn_counter.most_common():
        print(f"  {val}: {cnt}")
    if not iucn_counter:
        print("  (none / all NULL)")

    print("\nUnique 'Gefährdungsstatus' values from JSON (with counts):")
    for val, cnt in g_status_counter.most_common():
        print(f"  {val}: {cnt}")
    if not g_status_counter:
        print("  (none found)")

    print("\nMost common pairs: (Gefährdungsstatus → iucn_conservation_status)")
    for (g, i), cnt in pair_counter.most_common(20):
        print(f"  {g}  →  {i}  ({cnt})")
    if not pair_counter:
        print("  (no rows with both present)")

    # Suggest a mapping by short code → most frequent English label seen
    print("\nSuggested mapping (by short code, inferred from data):")
    # Canonical IUCN names (fallbacks if a code has no co-occurrence)
    canonical = {
        "NE": "Not Evaluated",
        "DD": "Data Deficient",
        "LC": "Least Concern",
        "NT": "Near Threatened",
        "VU": "Vulnerable",
        "EN": "Endangered",
        "CR": "Critically Endangered",
        "EW": "Extinct in the Wild",
        "EX": "Extinct",
    }
    code_to_iucn_counts = defaultdict(Counter)
    for (g, i), cnt in pair_counter.items():
        m = CODE_RE.match(g)
        if m:
            code_to_iucn_counts[m.group(1)][i] += cnt

    for code in sorted(set(list(code_to_full.keys()) + list(canonical.keys()))):
        if code_to_iucn_counts[code]:
            best, _ = code_to_iucn_counts[code].most_common(1)[0]
            print(f"  {code} → {best}")
        elif code in canonical and code in code_to_full:
            # Seen in German JSON but no English co-occurrence — propose canonical
            print(f"  {code} → {canonical[code]}  (canonical suggestion)")
        elif code in canonical and code not in code_to_full:
            # Not seen at all; still show canonical for completeness
            pass

    con.close()

if __name__ == "__main__":
    main()

