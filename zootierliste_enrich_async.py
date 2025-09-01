#!/usr/bin/env python3
"""
Asynchronously enrich the `animal` table with Wikipedia links and
basic taxonomic details from Wikidata for taxa that already have a
Wikidata Q-ID.

For each row, the script fetches the following data and updates missing
fields or overwrites them if ``--all`` is passed:
* English and German Wikipedia titles
* taxon rank
* parent taxon
* IUCN conservation status

Usage::

    python zootierliste_enrich_async.py [--db PATH] [--all]

``--db``   path to the SQLite database (default: ``zootierliste.db``)
``--all``  fetch data for all rows with a Q-ID instead of only those
           where any of the above fields are missing.

Network I/O is fully asynchronous (``httpx`` with HTTP/2); SQLite is
accessed with ``aiosqlite``.

Requires:
    pip install --upgrade httpx[http2] aiosqlite
"""

from __future__ import annotations

import argparse
import asyncio
import random
from typing import Any, Mapping

import aiosqlite
import httpx

# ────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────
DB_PATH = "zootierliste.db"

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

USER_AGENT = (
    "ZootierlisteBot/3.0 "
    "(https://example.org; philipp@example.org) "
    "python-httpx-async"
)
HEADERS = {"User-Agent": USER_AGENT}

CONCURRENT_REQ = 15          # parallel HTTP requests
SPARQL_RETRIES = 4
BASE_BACKOFF = 0.5           # seconds


# ────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────
def qid_from_uri(uri: str) -> str:
    """Convert https://www.wikidata.org/entity/Q123 → Q123"""
    return uri.rsplit("/", 1)[-1]


def _backoff(attempt: int) -> float:
    """Exponential back‑off with jitter."""
    return BASE_BACKOFF * 2 ** attempt + random.uniform(0, 0.25)


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    params: Mapping[str, Any],
    retries: int,
) -> Mapping[str, Any] | None:
    """GET → JSON with automatic retries on transient errors."""
    for att in range(retries):
        try:
            r = await client.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                429, 502, 503, 504
            }:
                raise
            await asyncio.sleep(_backoff(att))
    return None


async def sparql(client: httpx.AsyncClient, query: str) -> Mapping[str, Any] | None:
    """Run a SPARQL query with retry handling."""
    return await fetch_json(
        client,
        SPARQL_ENDPOINT,
        {"query": query, "format": "json"},
        SPARQL_RETRIES,
    )

# ────────────────────────────────────────────────────────
# 2.  SPARQL builders
# ────────────────────────────────────────────────────────
def build_wiki_query(qid: str, lang: str) -> str:
    return f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX schema: <http://schema.org/>
    SELECT (SAMPLE(?wikiTitle) AS ?wiki)
    WHERE {{
      BIND(wd:{qid} AS ?item)
      OPTIONAL {{
        ?article schema:about ?item;
                 schema:isPartOf <https://{lang}.wikipedia.org/>;
                 schema:inLanguage "{lang}";
                 schema:name ?wikiTitle.
      }}
    }}
    GROUP BY ?item
    LIMIT 1
    """


def build_details_query(qid: str) -> str:
    return f"""
    PREFIX wd:   <http://www.wikidata.org/entity/>
    PREFIX wdt:  <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT
      (SAMPLE(?rankLbl) AS ?rankLabel)
      (SAMPLE(?iucnLbl) AS ?iucnLabel)
      ?parent
    WHERE {{
      BIND(wd:{qid} AS ?item)

      OPTIONAL {{
        ?item wdt:P105 ?rank.
        ?rank rdfs:label ?rankLbl FILTER(LANG(?rankLbl)="en")
      }}

      OPTIONAL {{ ?item wdt:P171 ?parent. }}

      OPTIONAL {{
        ?item wdt:P141 ?iucn.
        ?iucn rdfs:label ?iucnLbl FILTER(LANG(?iucnLbl)="en")
      }}
    }}
    GROUP BY ?parent
    LIMIT 1
    """


# ────────────────────────────────────────────────────────
# 3.  Fetchers
# ────────────────────────────────────────────────────────
async def fetch_wikipedia(
    client: httpx.AsyncClient,
    qid: str,
    lang: str,
) -> dict[str, str]:
    data = await sparql(client, build_wiki_query(qid, lang))
    if not data or not data['results']['bindings']:
        return {}
    title = data['results']['bindings'][0].get('wiki', {}).get('value', '')
    if not title:
        return {}
    return {
        f"wikipedia_{lang}": f"https://{lang}.wikipedia.org/wiki/" + title.replace(' ', '_')
    }

async def fetch_details(client: httpx.AsyncClient, qid: str) -> dict[str, str]:
    data = await sparql(client, build_details_query(qid))
    if not data or not data["results"]["bindings"]:
        return {}

    b = data["results"]["bindings"][0]
    return {
        "taxon_rank": b.get("rankLabel", {}).get("value", ""),
        "parent_taxon": qid_from_uri(b.get("parent", {}).get("value", "")),
        "iucn_conservation_status": b.get("iucnLabel", {}).get("value", ""),
    }


# ────────────────────────────────────────────────────────
# 4.  Column check helpers
# ────────────────────────────────────────────────────────
MISSING_CHECKS = {
    "en": ("wikipedia_en",),
    "de": ("wikipedia_de",),
    "details": ("taxon_rank", "parent_taxon", "iucn_conservation_status"),
}


def needs_update(columns: tuple[str, ...], row: tuple[Any, ...], indices: dict[str, int]) -> bool:
    """Return True if any of *columns* in *row* is NULL/empty."""
    return any(not row[indices[col]] for col in columns)


# ────────────────────────────────────────────────────────
# 5.  Worker – one row
# ────────────────────────────────────────────────────────
async def process_row(
    db: aiosqlite.Connection,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    row: tuple[Any, ...],
    idx: dict[str, int],
    update_all: bool,
):
    """Enrich **one** animal record."""

    async with sem:
        (
            animal_id,
            latin_name,
            wikidata_id,
            taxon_rank,
            parent_taxon,
            wikipedia_en,
            wikipedia_de,
            iucn_conservation_status,
        ) = row
        qid = wikidata_id

        # ------------------------------------------------------------
        # 2)  Decide what needs to be fetched
        # ------------------------------------------------------------
        tasks: list[asyncio.Task] = []
        if update_all or needs_update(MISSING_CHECKS["en"], row, idx):
            tasks.append(fetch_wikipedia(client, qid, "en"))
        if update_all or needs_update(MISSING_CHECKS["de"], row, idx):
            tasks.append(fetch_wikipedia(client, qid, "de"))
        if update_all or needs_update(MISSING_CHECKS["details"], row, idx):
            tasks.append(fetch_details(client, qid))

        if not tasks:  # nothing to do
            return

        results = await asyncio.gather(*tasks)

        # ------------------------------------------------------------
        # 3)  Current DB values – used to avoid overwriting with empty
        #     strings or downgrading existing data.
        # ------------------------------------------------------------
        current = {
            "taxon_rank": taxon_rank,
            "parent_taxon": parent_taxon,
            "wikipedia_en": wikipedia_en,
            "wikipedia_de": wikipedia_de,
            "iucn_conservation_status": iucn_conservation_status,
        }

        update: dict[str, Any] = {}

        # ------------------------------------------------------------
        # 4)  Walk through every individual key/value returned and take
        #     it if it improves the record.
        # ------------------------------------------------------------
        for res in results:
            for key, val in res.items():
                if not val:
                    continue
                if key == "parent_taxon" and val == "":
                    continue
                if update_all:
                    if current.get(key) != val:
                        update[key] = val
                elif not current.get(key):
                    update[key] = val

        # ------------------------------------------------------------
        # 5)  Commit back to SQLite
        # ------------------------------------------------------------
        if update:
            placeholders = ", ".join(f"{k}=:{k}" for k in update)
            await db.execute(
                f"UPDATE animal SET {placeholders} WHERE animal_id=:aid",
                {**update, "aid": animal_id},
            )
            await db.commit()

            changed = ", ".join(update)
            print(f"[OK]   {latin_name:<40} ({qid}) → {changed}")


# ────────────────────────────────────────────────────────
# 6.  DB prep – add new columns if missing
# ────────────────────────────────────────────────────────
async def ensure_columns(db: aiosqlite.Connection) -> None:
    for col in (
        "wikidata_id TEXT",
        "taxon_rank TEXT",
        "parent_taxon TEXT",
        "wikipedia_en TEXT",
        "wikipedia_de TEXT",
        "iucn_conservation_status TEXT",
    ):
        try:
            await db.execute(f"ALTER TABLE animal ADD COLUMN {col}")
        except aiosqlite.OperationalError:
            pass  # column already exists
    await db.commit()


# ────────────────────────────────────────────────────────
# 7.  Main
# ────────────────────────────────────────────────────────
async def main(args: argparse.Namespace) -> None:
    sem = asyncio.Semaphore(CONCURRENT_REQ)

    async with (
        aiosqlite.connect(args.db) as db,
        httpx.AsyncClient(http2=True, headers=HEADERS, timeout=30) as client,
    ):
        await ensure_columns(db)

        col_idx = {
            "animal_id": 0,
            "latin_name": 1,
            "wikidata_id": 2,
            "taxon_rank": 3,
            "parent_taxon": 4,
            "wikipedia_en": 5,
            "wikipedia_de": 6,
            "iucn_conservation_status": 7,
        }

        if args.all:
            query = """
            SELECT
              animal_id,
              latin_name,
              wikidata_id,
              taxon_rank,
              parent_taxon,
              wikipedia_en,
              wikipedia_de,
              iucn_conservation_status
            FROM animal
            WHERE wikidata_id IS NOT NULL AND wikidata_id != ''
            ORDER BY zoo_count DESC
            """
        else:
            query = """
            SELECT
              animal_id,
              latin_name,
              wikidata_id,
              taxon_rank,
              parent_taxon,
              wikipedia_en,
              wikipedia_de,
              iucn_conservation_status
            FROM animal
            WHERE wikidata_id IS NOT NULL AND wikidata_id != ''
              AND (
                wikipedia_en IS NULL OR wikipedia_en = '' OR
                wikipedia_de IS NULL OR wikipedia_de = '' OR
                taxon_rank IS NULL OR taxon_rank = '' OR
                parent_taxon IS NULL OR parent_taxon = '' OR
                iucn_conservation_status IS NULL OR iucn_conservation_status = ''
              )
            ORDER BY zoo_count DESC
            """

        async with db.execute(query) as cur:
            rows = await cur.fetchall()

        print(f"Processing {len(rows)} taxa…")
        await asyncio.gather(
            *(process_row(db, client, sem, row, col_idx, args.all) for row in rows)
        )
        print("Finished.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich animal table from Wikidata")
    parser.add_argument(
        "--db", default=DB_PATH, help="path to SQLite database (default: %(default)s)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Fetch for all rows that have a wikidata_id (default: only rows with a "
            "wikidata_id AND any of wikipedia_en, wikipedia_de, taxon_rank, "
            "parent_taxon, iucn_conservation_status missing)"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
