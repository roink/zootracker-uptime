#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import os
import time
import re
from urllib.parse import urlparse, parse_qs
import sqlite3
import json
import csv
from dataclasses import dataclass

BASE_URL      = "https://www.zootierliste.de/index.php"
DB_FILE       = "zootierliste.db"
SLEEP_SECONDS = 1
MAP_ZOOS_URL  = "https://www.zootierliste.de/map_zoos.php"



def get_links(params, pattern, description):
    print(f"[+] Fetching {description}: {params}")
    r = requests.get(BASE_URL, params=params)
    r.raise_for_status()
    time.sleep(SLEEP_SECONDS)
    soup = BeautifulSoup(r.text, "html.parser")
    found = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(pattern, href):
            found.add(requests.compat.urljoin(BASE_URL, href))
    found = sorted(found)
    print(f"    → {len(found)} found.")
    return found


def parse_species(species_url):
    print(f"[>] Fetching species page: {species_url}")
    r = requests.get(species_url)
    r.raise_for_status()
    time.sleep(SLEEP_SECONDS)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Page name (like async version), stripped of any parenthesized suffix
    page_td = soup.find('td', class_='pageName')
    raw_name = page_td.get_text(" ", strip=True) if page_td else ''
    page_name = re.sub(r"\s*\(.*?\)", "", raw_name).strip()

    # Description table (like async version)
    desc_table = soup.find('table', attrs={'style': re.compile(r"max-width:500px")})
    desc = {}
    if desc_table:
        for row in desc_table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True).rstrip(':')
                if key:
                    desc[key] = cols[1].get_text(" ", strip=True)

    # Latin name
    latin = None
    for td in soup.find_all("td", id="tagline"):
        if (i := td.find("i")):
            latin = i.text.strip()
            break

    # Zoos with continent, country, city & zoo name
    zoos = []
    for tab in soup.find_all("table", id="tab"):
        cont_td = tab.find("td", {"align": "center", "id": "tagline"})
        if not cont_td or not (cont_a := cont_td.find("a")):
            continue
        continent = cont_a.text.strip()

        for row in tab.find_all("tr", class_=re.compile(r"^kontinent_\d+$")):
            country_a = row.find("a", onclick=re.compile(r"toggleTagVisibility"))
            if not country_a:
                continue
            country = re.sub(r"\s*\([^)]*\):?", "", country_a.text.strip())

            div = row.find("div", id=re.compile(r"_zoos$"))
            if not div:
                continue

            for zoo_a in div.find_all("a", onclick=re.compile(r"overlib")):
                raw = zoo_a.text.strip()
                m = re.match(r"^\s*([^(]+?)\s*\((.*)\)\s*$", raw)
                if m:
                    city = m.group(1).strip()
                    name = m.group(2).strip()
                    name = re.sub(r"\s*\(ehemals[^)]*\)", "", name).strip()
                else:
                    city = ''
                    name = raw

                zoos.append({
                    "continent": continent,
                    "country": country,
                    "city": city,
                    "name": name
                })
    print(f"    → Latin: {latin}, Zoos found: {len(zoos)}, Page: {page_name}, Desc: {len(desc)} fields")
    return latin, zoos, page_name, desc


@dataclass(frozen=True)
class ZooLocation:
    zoo_id: int
    latitude: float
    longitude: float


def fetch_zoo_map_soup(animal_id: int) -> BeautifulSoup:
    """Fetch zoo map data for a given animal ID and return the BeautifulSoup."""
    params = {"art": str(animal_id), "tab": "tab_zootier"}
    r = requests.get(MAP_ZOOS_URL, params=params, timeout=(5, 20))
    r.raise_for_status()
    time.sleep(SLEEP_SECONDS)
    return BeautifulSoup(r.text, "html.parser")


def parse_zoo_map(soup: BeautifulSoup) -> list[ZooLocation]:
    """Return list of ZooLocation instances from map soup."""
    results: list[ZooLocation] = []
    text = soup.get_text().lstrip("\ufeff")
    reader = csv.reader(text.splitlines(), delimiter="\t")
    next(reader, None)  # Skip header
    for row in reader:
        if not row or len(row) < 2:
            continue
        latlon, zoo_id = row[0], row[1]
        try:
            lat_str, lon_str = latlon.split(",", 1)
            lat = float(lat_str)
            lon = float(lon_str)
            results.append(ZooLocation(int(zoo_id), lat, lon))
        except ValueError:
            continue
    return results


def ensure_db_schema(conn):
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS animal (
            animal_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            klasse      INTEGER,
            ordnung     INTEGER,
            familie     INTEGER,
            art         TEXT,
            latin_name  TEXT,
            UNIQUE(klasse, ordnung, familie, art, latin_name)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS zoo (
            zoo_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            continent   TEXT,
            country     TEXT,
            city        TEXT,
            name        TEXT,
            UNIQUE(continent, country, city, name)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS zoo_animal (
            zoo_id      INTEGER,
            animal_id   INTEGER,
            PRIMARY KEY(zoo_id, animal_id),
            FOREIGN KEY(zoo_id) REFERENCES zoo(zoo_id),
            FOREIGN KEY(animal_id) REFERENCES animal(animal_id)
        )
    """)
    # Add enrichment columns if missing (non-destructive)
    cols = {row[1] for row in c.execute("PRAGMA table_info(animal)").fetchall()}
    if 'zootierliste_description' not in cols:
        c.execute("ALTER TABLE animal ADD COLUMN zootierliste_description TEXT")
    if 'zootierliste_name' not in cols:
        c.execute("ALTER TABLE animal ADD COLUMN zootierliste_name TEXT")
    conn.commit()

def update_animal_enrichment(conn, animal_id, page_name, desc_dict):
    """Store page name and description JSON on the animal row."""
    desc_json = json.dumps(desc_dict or {}, ensure_ascii=False)
    c = conn.cursor()
    c.execute(
        "UPDATE animal SET zootierliste_description = ?, zootierliste_name = ? WHERE animal_id = ?",
        (desc_json, page_name, animal_id)
    )
    conn.commit()

def get_or_create_animal(conn, klasse, ordnung, familie, art_id, latin_name):
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO animal (klasse, ordnung, familie, art, latin_name) VALUES (?, ?, ?, ?, ?)",
        (klasse, ordnung, familie, art_id, latin_name)
    )
    conn.commit()
    c.execute(
        "SELECT animal_id FROM animal WHERE klasse=? AND ordnung=? AND familie=? AND art=? AND latin_name=?",
        (klasse, ordnung, familie, art_id, latin_name)
    )
    return c.fetchone()[0]


def get_or_create_zoo(conn, continent, country, city, name):
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO zoo (continent, country, city, name) VALUES (?, ?, ?, ?)",
        (continent, country, city, name)
    )
    conn.commit()
    c.execute(
        "SELECT zoo_id FROM zoo WHERE continent=? AND country=? AND city=? AND name=?",
        (continent, country, city, name)
    )
    return c.fetchone()[0]


def create_zoo_animal(conn, zoo_id, animal_id):
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO zoo_animal (zoo_id, animal_id) VALUES (?, ?)",
        (zoo_id, animal_id)
    )
    conn.commit()



def main():
    conn = sqlite3.connect(DB_FILE)
    ensure_db_schema(conn)
    cursor = conn.cursor()

    for klasse in [1]:
        print(f"\n=== CLASS {klasse} ===")
        orders = get_links(
            {"klasse": klasse},
            fr"\?klasse={klasse}&ordnung=\d+$",
            f"orders in class {klasse}"
        )

        for ord_url in orders:
            ordnung = parse_qs(urlparse(ord_url).query)["ordnung"][0]
            families = get_links(
                {"klasse": klasse, "ordnung": ordnung},
                fr"\?klasse={klasse}&ordnung={ordnung}&familie=\d+$",
                f"families in {klasse}/{ordnung}"
            )

            for fam_url in families:
                familie = parse_qs(urlparse(fam_url).query)["familie"][0]
                species_list = get_links(
                    {"klasse": klasse, "ordnung": ordnung, "familie": familie},
                    fr"\?klasse={klasse}&ordnung={ordnung}&familie={familie}&art=\d+",
                    f"species in {klasse}/{ordnung}/{familie}"
                )

                for sp_url in species_list:
                    art_id = parse_qs(urlparse(sp_url).query)["art"][0]

                    # Skip if this species is already in the database
                    cursor.execute(
                        "SELECT animal_id FROM animal WHERE klasse=? AND ordnung=? AND familie=? AND art=?",
                        (klasse, ordnung, familie, art_id)
                    )
                    if cursor.fetchone():
                        print(f"    → Skipping species art={art_id}, already in DB")
                        continue

                    try:
                        latin, zoos, page_name, desc = parse_species(sp_url)
                        if latin is None:
                            print(f"    ! Skipping species art={art_id} ({sp_url}) – missing Latin name.")
                            continue
                        animal_id = get_or_create_animal(
                            conn, klasse, ordnung, familie, art_id, latin
                        )
                        # store enrichment (page name + description) for the animal
                        update_animal_enrichment(conn, animal_id, page_name, desc)
                        for z in zoos:
                            zoo_id = get_or_create_zoo(
                                conn,
                                z["continent"],
                                z["country"],
                                z["city"],
                                z["name"]
                            )
                            create_zoo_animal(conn, zoo_id, animal_id)
                    except Exception as e:
                        print(f"[!] Error processing species art={art_id}: {e}")

    conn.close()

if __name__ == "__main__":
    main()

