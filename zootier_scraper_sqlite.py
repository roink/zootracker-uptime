#!/usr/bin/env python3
import html
import os
import time
import re
from urllib.parse import urlparse, parse_qs
import sqlite3
import json
import csv
from dataclasses import dataclass
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

BASE_URL      = "https://www.zootierliste.de/index.php"
DB_FILE       = "zootierliste.db"
SLEEP_SECONDS = 1
MAP_ZOOS_URL  = "https://www.zootierliste.de/map_zoos.php"

HEADERS = {"User-Agent": "Mozilla/5.0"}
AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _session_with_retries() -> requests.Session:
    sess = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    sess.headers.update(HEADERS)
    return sess


SESSION = _session_with_retries()


def get_links(params, pattern, description):
    print(f"[+] Fetching {description}: {params}")
    r = SESSION.get(BASE_URL, params=params)
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
    r = SESSION.get(species_url)
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

@dataclass(frozen=True)
class ZooInfo:
    country: Optional[str]
    website: Optional[str]
    city: Optional[str]
    name: Optional[str]


def fetch_zoo_popup_soup(zoo_id: int, session: requests.Session | None = None) -> BeautifulSoup:
    sess = session or SESSION
    r = sess.get(
        MAP_ZOOS_URL,
        params={"showzoo": str(zoo_id), "popup": "true"},
        headers=AJAX_HEADERS,
        timeout=(5, 20),
    )
    r.raise_for_status()
    time.sleep(SLEEP_SECONDS)
    return BeautifulSoup(r.text, "html.parser")


def parse_zoo_popup(soup: BeautifulSoup) -> ZooInfo:
    city = name = None
    title = soup.select_one("div.datum")
    if title:
        raw = title.get_text(strip=True)
        m = re.match(r"^\s*(.*?)\s*\((.*?)\)\s*$", raw)
        if m:
            city, name = m.group(1).strip(), m.group(2).strip()
        else:
            city = raw.strip()

    country = website = None
    info = soup.select_one("div.inhalt")
    if info:
        html_block = info.decode_contents().replace("&nbsp;", " ")
        m_country = re.search(r"Land:\s*([^<]+)", html_block, flags=re.IGNORECASE)
        if m_country:
            country = html.unescape(m_country.group(1)).strip()
        link = info.find("a", href=True)
        if link:
            website = link["href"].strip()

    return ZooInfo(country=country, website=website, city=city, name=name)


def fetch_zoo_details(zoo_id: int) -> dict:
    """Backwards-compatible wrapper returning a dict of zoo details."""
    soup = fetch_zoo_popup_soup(zoo_id)
    info = parse_zoo_popup(soup)
    return {
        "country": info.country or "",
        "website": info.website or "",
        "city": info.city or "",
        "name": info.name or "",
    }


def fetch_zoo_map_soup(art: int) -> BeautifulSoup:
    """Fetch zoo map data for a given animal art code and return the BeautifulSoup."""
    params = {"art": str(art), "tab": "tab_zootier"}
    r = SESSION.get(MAP_ZOOS_URL, params=params, timeout=(5, 20))
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
    c.execute("PRAGMA foreign_keys = ON;")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS animal (
            art         TEXT PRIMARY KEY,
            klasse      INTEGER,
            ordnung     INTEGER,
            familie     INTEGER,
            latin_name  TEXT,
            zootierliste_description TEXT,
            zootierliste_name        TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS zoo (
            zoo_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            continent   TEXT,
            country     TEXT,
            city        TEXT,
            name        TEXT,
            UNIQUE(continent, country, city, name)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS zoo_animal (
            zoo_id      INTEGER,
            art         TEXT,
            PRIMARY KEY(zoo_id, art),
            FOREIGN KEY(zoo_id) REFERENCES zoo(zoo_id),
            FOREIGN KEY(art) REFERENCES animal(art)
        )
        """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS zoo_name_idx ON zoo(country, city, name);
        """
    )
    conn.commit()

def update_animal_enrichment(conn, art, page_name, desc_dict):
    """Store page name and description JSON on the animal row."""
    desc_json = json.dumps(desc_dict or {}, ensure_ascii=False)
    c = conn.cursor()
    c.execute(
        "UPDATE animal SET zootierliste_description = ?, zootierliste_name = ? WHERE art = ?",
        (desc_json, page_name, art)
    )
    conn.commit()

def get_or_create_animal(conn, klasse, ordnung, familie, art, latin_name):
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO animal (art, klasse, ordnung, familie, latin_name) VALUES (?, ?, ?, ?, ?)",
        (art, klasse, ordnung, familie, latin_name)
    )
    conn.commit()
    return art


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


def create_zoo_animal(conn, zoo_id, art):
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO zoo_animal (zoo_id, art) VALUES (?, ?)",
        (zoo_id, art)
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
                    art = parse_qs(urlparse(sp_url).query)["art"][0]

                    # Skip if this species is already in the database
                    cursor.execute(
                        "SELECT art FROM animal WHERE klasse=? AND ordnung=? AND familie=? AND art=?",
                        (klasse, ordnung, familie, art)
                    )
                    if cursor.fetchone():
                        print(f"    → Skipping species art={art}, already in DB")
                        continue

                    try:
                        latin, zoos, page_name, desc = parse_species(sp_url)
                        if latin is None:
                            print(f"    ! Skipping species art={art} ({sp_url}) – missing Latin name.")
                            continue
                        art_key = get_or_create_animal(
                            conn, klasse, ordnung, familie, art, latin
                        )
                        # store enrichment (page name + description) for the animal
                        update_animal_enrichment(conn, art_key, page_name, desc)
                        for z in zoos:
                            zoo_id = get_or_create_zoo(
                                conn,
                                z["continent"],
                                z["country"],
                                z["city"],
                                z["name"]
                            )
                            create_zoo_animal(conn, zoo_id, art_key)
                    except Exception as e:
                        print(f"[!] Error processing species art={art}: {e}")

    conn.close()

if __name__ == "__main__":
    main()

