#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fill English country names in SQLite table `country_name`.

Usage:
  python fill_country_name_en.py path/to/your.db
Options:
  --force            Update even if name_en is already set (default: only fill empty/NULL)
  --dry-run          Don't write changes, just show what would change
  --verbose          Print each update line-by-line

Notes:
- English names follow UN/ISO usage (e.g., "Côte d'Ivoire", "Czechia").
- Territories use "Country/Territory" (e.g., "France/French Polynesia").
- If you prefer "Turkey" instead of "Türkiye", adjust the mapping below.
"""

from __future__ import annotations
import argparse
import sqlite3
from typing import Dict, List, Tuple, Optional

# Exact German -> English mapping
# Keys must match `country_name.name_de` exactly.
DE_TO_EN: Dict[str, str] = {
    "Afghanistan": "Afghanistan",
    "Albanien": "Albania",
    "Andorra": "Andorra",
    "Angola": "Angola",
    "Argentinien": "Argentina",
    "Armenien": "Armenia",
    "Aserbaidschan": "Azerbaijan",
    "Australien": "Australia",
    "Australien/Weihnachtsinsel": "Australia/Christmas Island",
    "Bahamas": "Bahamas",
    "Bahrain": "Bahrain",
    "Bangladesch": "Bangladesh",
    "Belarus": "Belarus",
    "Belgien": "Belgium",
    "Belize": "Belize",
    "Bhutan": "Bhutan",
    "Bolivien": "Bolivia",
    "Bosnien-Herzegowina": "Bosnia and Herzegovina",
    "Botsuana": "Botswana",
    "Brasilien": "Brazil",
    "Brunei Darussalam": "Brunei Darussalam",
    "Bulgarien": "Bulgaria",
    "Cabo Verde": "Cabo Verde",
    "Chile": "Chile",
    "China": "China",
    "China/Hongkong": "China/Hong Kong",
    # ISO/UN use "Macao" as the short form; "Macau" is also common. 
    "China/Macau": "China/Macao",
    "Costa Rica": "Costa Rica",
    "Demokratische Republik Kongo": "Democratic Republic of the Congo",
    "Deutschland": "Germany",
    "Dominikanische Republik": "Dominican Republic",
    "Dschibuti": "Djibouti",
    "Dänemark": "Denmark",
    "Dänemark/Färöer": "Denmark/Faroe Islands",
    "Ecuador": "Ecuador",
    "El Salvador": "El Salvador",
    "Elfenbeinküste": "Côte d'Ivoire",
    "Estland": "Estonia",
    "Fidschi": "Fiji",
    "Finnland": "Finland",
    "Frankreich": "France",
    "Frankreich/Französisch-Guayana": "France/French Guiana",
    "Frankreich/Französisch-Polynesien": "France/French Polynesia",
    "Frankreich/Guadeloupe": "France/Guadeloupe",
    "Frankreich/Martinique": "France/Martinique",
    "Frankreich/Neukaledonien": "France/New Caledonia",
    "Gabun": "Gabon",
    "Georgien": "Georgia",
    "Ghana": "Ghana",
    "Griechenland": "Greece",
    "Guatemala": "Guatemala",
    "Haiti": "Haiti",
    "Honduras": "Honduras",
    "Indien": "India",
    "Indonesien": "Indonesia",
    "Irak": "Iraq",
    "Iran": "Iran",
    "Irland": "Ireland",
    "Island": "Iceland",
    "Israel": "Israel",
    "Italien": "Italy",
    "Jamaika": "Jamaica",
    "Japan": "Japan",
    "Jemen": "Yemen",
    "Jordanien": "Jordan",
    "Kambodscha": "Cambodia",
    "Kamerun": "Cameroon",
    "Kanada": "Canada",
    "Kasachstan": "Kazakhstan",
    "Kenia": "Kenya",
    "Kirgisistan": "Kyrgyzstan",
    "Kolumbien": "Colombia",
    "Kosovo": "Kosovo",
    "Kroatien": "Croatia",
    "Kuba": "Cuba",
    "Kuwait": "Kuwait",
    "Laos": "Laos",
    "Lettland": "Latvia",
    "Libanon": "Lebanon",
    "Liechtenstein": "Liechtenstein",
    "Litauen": "Lithuania",
    "Luxemburg": "Luxembourg",
    "Madagaskar": "Madagascar",
    "Malaysia": "Malaysia",
    "Malediven": "Maldives",
    "Malta": "Malta",
    "Marokko": "Morocco",
    "Mauritius": "Mauritius",
    "Mexiko": "Mexico",
    "Moldawien": "Moldova",
    "Monaco": "Monaco",
    "Montenegro": "Montenegro",
    "Myanmar": "Myanmar",
    "Namibia": "Namibia",
    "Nepal": "Nepal",
    "Neuseeland": "New Zealand",
    "Nicaragua": "Nicaragua",
    "Niederlande": "Netherlands",
    "Niederlande/Aruba": "Netherlands/Aruba",
    "Niederlande/Bonaire": "Netherlands/Bonaire",
    "Niederlande/Curacao": "Netherlands/Curaçao",
    "Niederlande/Sint Maarten": "Netherlands/Sint Maarten",
    "Nigeria": "Nigeria",
    "Nordkorea": "North Korea",
    "Nordmazedonien": "North Macedonia",
    "Norwegen": "Norway",
    "Oman": "Oman",
    "Pakistan": "Pakistan",
    "Palau": "Palau",
    "Panama": "Panama",
    "Papua-Neuguinea": "Papua New Guinea",
    "Paraguay": "Paraguay",
    "Peru": "Peru",
    "Philippinen": "Philippines",
    "Polen": "Poland",
    "Portugal": "Portugal",
    "Republik Kongo": "Republic of the Congo",
    "Ruanda": "Rwanda",
    "Rumänien": "Romania",
    "Russland": "Russia",
    "Sambia": "Zambia",
    "Saudi-Arabien": "Saudi Arabia",
    "Schweden": "Sweden",
    "Schweiz": "Switzerland",
    "Senegal": "Senegal",
    "Serbien": "Serbia",
    "Sierra Leone": "Sierra Leone",
    "Simbabwe": "Zimbabwe",
    "Singapur": "Singapore",
    "Slowakei": "Slovakia",
    "Slowenien": "Slovenia",
    "Somalia/Somaliland": "Somalia/Somaliland",
    "Spanien": "Spain",
    "Sri Lanka": "Sri Lanka",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "Sudan": "Sudan",
    "Suriname": "Suriname",
    "Syrien": "Syria",
    "Südafrika": "South Africa",
    "Südkorea": "South Korea",
    "Tadschikistan": "Tajikistan",
    "Taiwan": "Taiwan",
    "Tansania": "Tanzania",
    "Thailand": "Thailand",
    "Togo": "Togo",
    "Trinidad und Tobago": "Trinidad and Tobago",
    "Tschechien": "Czechia",
    "Tunesien": "Tunisia",
    "Türkei": "Türkiye",
    "Uganda": "Uganda",
    "Ukraine": "Ukraine",
    "Ukraine/Krim": "Ukraine/Crimea",
    "Ungarn": "Hungary",
    "Uruguay": "Uruguay",
    "Usbekistan": "Uzbekistan",
    "Vanuatu": "Vanuatu",
    "Venezuela": "Venezuela",
    "Vereinigte Arabische Emirate": "United Arab Emirates",
    "Vereinigte Staaten": "United States",
    "Vereinigte Staaten/Jungferninseln": "United States/Virgin Islands",
    "Vereinigte Staaten/Guam": "United States/Guam",
    "Vereinigtes Königreich": "United Kingdom",
    "Vereinigtes Königreich/Bailiwick of Jersey": "United Kingdom/Bailiwick of Jersey",
    "Vereinigtes Königreich/Bermuda": "United Kingdom/Bermuda",
    "Vereinigtes Königreich/Cayman Island": "United Kingdom/Cayman Islands",
    "Vereinigtes Königreich/Gibraltar": "United Kingdom/Gibraltar",
    "Vereinigtes Königreich/Isle of Man": "United Kingdom/Isle of Man",
    "Vietnam": "Vietnam",
    "Zypern": "Cyprus",
    "Zypern/Nordzypern": "Cyprus/Northern Cyprus",
    "Ägypten": "Egypt",
    "Äthiopien": "Ethiopia",
    "Österreich": "Austria",
}

def normalize(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s if s != "" else None

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("db", help="Path to SQLite database")
    ap.add_argument("--force", action="store_true", help="Overwrite existing non-empty name_en")
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    ap.add_argument("--verbose", action="store_true", help="Print each row updated")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Basic schema sanity checks
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='country_name'")
    if cur.fetchone() is None:
        raise SystemExit("Table 'country_name' not found.")

    cur.execute("PRAGMA table_info(country_name)")
    cols = {row["name"] for row in cur.fetchall()}
    required = {"id", "name_de", "name_en"}
    missing = required - cols
    if missing:
        raise SystemExit(f"Missing columns in 'country_name': {', '.join(sorted(missing))}")

    # Read current rows
    cur.execute("SELECT id, name_de, name_en FROM country_name ORDER BY id")
    rows = cur.fetchall()

    updates: List[Tuple[str, int]] = []
    unmapped: List[Tuple[int, str]] = []
    already_ok = 0

    for row in rows:
        rid = row["id"]
        de = normalize(row["name_de"])
        en_current = normalize(row["name_en"])

        if de is None:
            continue

        en_target = DE_TO_EN.get(de)

        if en_target is None:
            unmapped.append((rid, de))
            continue

        if en_current and not args.force:
            already_ok += 1
            continue

        if en_current == en_target:
            already_ok += 1
            continue

        updates.append((en_target, rid))
        if args.verbose:
            print(f"[UPDATE] id={rid}  {de!r}  ->  {en_target!r}")

    print(f"Found {len(rows)} rows; will update {len(updates)} rows; already OK: {already_ok}; unmapped: {len(unmapped)}")

    if unmapped:
        print("\nUnmapped German names (please add to DE_TO_EN):")
        for rid, de in unmapped:
            print(f"  id={rid}: {de}")

    if updates and not args.dry_run:
        cur.executemany("UPDATE country_name SET name_en = ? WHERE id = ?", updates)
        conn.commit()
        print(f"Committed {len(updates)} updates.")
    elif updates and args.dry_run:
        print("(dry-run) No changes written.")
    else:
        print("Nothing to do.")

    conn.close()

if __name__ == "__main__":
    main()

