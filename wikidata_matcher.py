#!/usr/bin/env python3
"""Simplified Wikidata matcher.

For each animal in the database, query Wikidata individually to find a
matching QID. The lookup tries a direct SPARQL P225 match first and falls
back to the `wbsearchentities` API. Only the QID is fetched; additional
labels or metadata are ignored.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import Optional, Sequence

import httpx

from zootier_scraper_sqlite import DB_FILE, ensure_db_schema

SPARQL_URL = "https://query.wikidata.org/sparql"
API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "ZooTracker/1.0 (contact: contact@zootracker.app)"
MAX_API_RETRIES = 5


def _escape(name: str) -> str:
    """Escape for inclusion inside single-quoted SPARQL string literals."""
    return name.replace("\\", "\\\\").replace("'", "\\'")


async def _sparql_taxon(client: httpx.AsyncClient, name: str) -> Optional[str]:
    """Return the QID for a taxon with exact P225 ``name``."""
    query = f"""
SELECT ?item WHERE {{
  ?item wdt:P31 wd:Q16521;
        wdt:P225 '{_escape(name)}'.
}} LIMIT 1
"""
    r = await client.post(
        SPARQL_URL,
        data={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    r.raise_for_status()
    bindings = r.json().get("results", {}).get("bindings", [])
    if not bindings:
        return None
    return bindings[0]["item"]["value"].rsplit("/", 1)[-1]


async def _search_wikidata_api(
    client: httpx.AsyncClient, name: str, language: str = "en", limit: int = 10
) -> Sequence[str]:
    delay = 1.0
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": language,
        "format": "json",
        "type": "item",
        "limit": limit,
    }
    for _ in range(MAX_API_RETRIES):
        r = await client.get(API_URL, params=params, headers={"User-Agent": USER_AGENT})
        if r.status_code == 429:
            await asyncio.sleep(delay)
            delay *= 2
            continue
        r.raise_for_status()
        return [entry["id"] for entry in r.json().get("search", [])]
    return []


async def _validate_qid(
    client: httpx.AsyncClient, latin_names: Sequence[str], qid: str
) -> bool:
    """Check that ``qid`` is a taxon whose P225 matches one of ``latin_names``."""
    query = f"""
SELECT ?tn WHERE {{
  wd:{qid} wdt:P31 wd:Q16521;
         wdt:P225 ?tn.
}} LIMIT 1
"""
    r = await client.post(
        SPARQL_URL,
        data={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    if r.status_code != 200:
        return False
    bindings = r.json().get("results", {}).get("bindings", [])
    if not bindings:
        return False
    tn = bindings[0]["tn"]["value"].lower()
    return any(tn == ln.lower() for ln in latin_names)


async def find_qid(client: httpx.AsyncClient, animal: dict) -> Optional[str]:
    """Return the best matching QID for ``animal`` or ``None``."""
    latin_names: list[str] = []
    if animal.get("normalized_latin_name"):
        latin_names.append(animal["normalized_latin_name"])
    try:
        latin_names.extend(
            [n for n in json.loads(animal.get("alternative_latin_names") or "[]") if n]
        )
    except json.JSONDecodeError:
        pass

    for name in latin_names:
        qid = await _sparql_taxon(client, name)
        if qid:
            return qid
        for candidate in await _search_wikidata_api(client, name):
            if await _validate_qid(client, latin_names, candidate):
                return candidate

    for field, lang in (("name_en", "en"), ("name_de", "de")):
        if not animal.get(field):
            continue
        for candidate in await _search_wikidata_api(client, animal[field], language=lang):
            if await _validate_qid(client, latin_names, candidate):
                return candidate
    return None


async def process_animals(
    db_path: str = DB_FILE, client: httpx.AsyncClient | None = None
) -> None:
    """Process all eligible animals and update their Wikidata QIDs."""
    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    cur = conn.cursor()
    cur.execute(
        """
SELECT art, normalized_latin_name, alternative_latin_names, name_en, name_de
FROM animal
WHERE klasse < 6
  AND qualifier IS NULL
  AND qualifier_target IS NULL
  AND locality IS NULL
  AND trade_code IS NULL
  AND wikidata_qid IS NULL
ORDER BY zoo_count DESC
"""
    )
    rows = cur.fetchall()
    assigned: set[str] = set()
    http_client = client or httpx.AsyncClient(timeout=30)
    if client is None:
        await http_client.__aenter__()
    try:
        http_client.headers.update({"User-Agent": USER_AGENT})
        for art, latin, alts, name_en, name_de in rows:
            animal = {
                "normalized_latin_name": latin,
                "alternative_latin_names": alts,
                "name_en": name_en,
                "name_de": name_de,
            }
            try:
                qid = await find_qid(http_client, animal)
            except Exception:
                qid = None
            if qid and qid not in assigned:
                conn.execute(
                    "UPDATE animal SET wikidata_qid=?, wikidata_match_status='auto' WHERE art=?",
                    (qid, art),
                )
                assigned.add(qid)
            elif qid:
                print(f"collision for {art}: {qid}")
                conn.execute(
                    "UPDATE animal SET wikidata_match_status='collision' WHERE art=?",
                    (art,),
                )
            else:
                conn.execute(
                    "UPDATE animal SET wikidata_match_status='none' WHERE art=?",
                    (art,),
                )
            conn.commit()
    finally:
        if client is None:
            await http_client.__aexit__(None, None, None)
        conn.close()


if __name__ == "__main__":  # pragma: no cover - manual invocation
    asyncio.run(process_animals())
