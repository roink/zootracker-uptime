#!/usr/bin/env python3
"""Use the OpenAI API to look up Wikidata QIDs.

This script queries the OpenAI Responses API for every animal in the
local database that is missing a ``wikidata_qid``.  The model is asked to
provide the correct Wikidata item identifier (``QID``) for the species
given its original Latin name as well as its German and English common
names.  The model must return ``null``/``unknown`` if no Wikidata entry is
found.  Returned identifiers are written back to the database only if no
other animal already uses the same QID.

The heavy lifting is delegated to :func:`process_animals` which accepts an
optional OpenAI client instance for easier testing.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Callable, Optional, Tuple

from matcher_shared import (
    apply_qid_update,
    ensure_enrichment_columns,
    fetch_wikidata_enrichment,
    lookup_rows,
    RESET_COLS,
)

try:  # pragma: no cover - fallback for environments without python-dotenv
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - library missing
    import os

    def load_dotenv(*args, **kwargs):  # type: ignore
        dotenv_path = kwargs.get("dotenv_path") if kwargs else None
        override = kwargs.get("override", False)
        if not dotenv_path:
            return False
        try:
            with open(dotenv_path, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    key, _, value = line.partition("=")
                    if key and (override or key not in os.environ):
                        os.environ[key] = value
            return True
        except OSError:
            return False
try:  # pragma: no cover - allow running without pydantic
    from pydantic import BaseModel
except Exception:  # pragma: no cover - library missing
    class BaseModel:  # type: ignore
        pass
from zootier_scraper_sqlite import DB_FILE, ensure_db_schema

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


class WikidataLookup(BaseModel):
    """Structured output parsed from the model response."""

    wikidata_qid: str | None = None


class CollisionLookup(BaseModel):
    """Structured output for resolving a QID collision."""

    existing_qid: str | None = None
    new_qid: str | None = None


_QID_RE = re.compile(r"^Q\d+$")
def update_enrichment(
    cur: sqlite3.Cursor, art: str, qid: str, fetch: Callable[[str], dict[str, str]] = fetch_wikidata_enrichment
) -> None:
    """Fetch metadata for *qid* and store it for *art*."""

    data = fetch(qid)
    update = {k: v for k, v in data.items() if v and not (k == "parent_taxon" and v == "")}
    if not update:
        return
    set_bits = ", ".join(f"{k}=?" for k in update)
    cur.execute(f"UPDATE animal SET {set_bits} WHERE art=?", (*update.values(), art))


def lookup_qid(client: Any, latin: str, name_de: Optional[str], name_en: Optional[str]) -> Optional[str]:
    """Query the OpenAI API and return a Wikidata QID or ``None``.

    Parameters
    ----------
    client:
        An object exposing ``responses.parse`` compatible with the OpenAI
        Python SDK.
    latin, name_de, name_en:
        Taxon names used to query the model.
    """

    prompt = (
        "Return the Wikidata QID for the taxon (species or subspecies). Do "
        "not return individuals, breeds, or disambiguation pages. If nothing "
        "suitable exists, return null.\n"
        f"Latin name: {latin}\n"
        f"German name: {name_de or 'unknown'}\n"
        f"English name: {name_en or 'unknown'}"
    )
    client_opt = (
        client.with_options(timeout=900.0)
        if hasattr(client, "with_options")
        else client
    )
    for attempt in range(3):
        try:
            resp = client_opt.responses.parse(
                model="gpt-5-mini",
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You find Wikidata QIDs for animal taxa. "
                            "Only return species/subspecies/varieties, not individuals or breeds. "
                            "If unsure or no taxon exists, return null."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=[{"type": "web_search"}],
                reasoning={
                    "effort": "high"
                },
                service_tier="flex",
                text_format=WikidataLookup,
            )
            qid = (resp.output_parsed.wikidata_qid or "").strip()
            if qid.lower() in {"", "none", "null", "unknown"}:
                return None
            if not _QID_RE.match(qid):
                return None
            return qid
        except Exception as exc:  # pragma: no cover - network faults
            status = getattr(exc, "status_code", None)
            if status in {408, 429} and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise
    return None


def resolve_collision(
    client: Any,
    existing: Tuple[str, str, Optional[str], Optional[str]],
    new: Tuple[str, str, Optional[str], Optional[str]],
    collided_qid: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Ask the model for QIDs for two colliding entries."""

    _e_art, e_latin, e_de, e_en = existing
    _n_art, n_latin, n_de, n_en = new
    prompt = (
        "Two different animal entries yielded the same Wikidata QID. "
        "Return exactly one Wikidata QID for EACH entry so they do NOT share the same QID. "
        "Rules:\n"
        "• If an entry is a subspecies (Latin has three terms like Genus species subspecies), "
        "  prefer a subspecies QID; if none exists, return null for that entry.\n"
        "• If an entry says 'sensu lato' (species complex), map it to the species-level item if appropriate, "
        "  but then the other entry MUST be a different QID or null.\n"
        "• Never return the same QID for both. If only one valid item exists, one entry must be null.\n"
        f"Previously returned (collided) QID: {collided_qid}\n"
        f"Entry A – Latin: {e_latin}\nGerman: {e_de or 'unknown'}\nEnglish: {e_en or 'unknown'}\n"
        f"Entry B – Latin: {n_latin}\nGerman: {n_de or 'unknown'}\nEnglish: {n_en or 'unknown'}"
    )
    client_opt = (
        client.with_options(timeout=900.0)
        if hasattr(client, "with_options")
        else client
    )
    for attempt in range(3):
        try:
            resp = client_opt.responses.parse(
                model="gpt-5-mini",
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You disambiguate animal taxa and provide distinct Wikidata QIDs. "
                            "Return null if unsure."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=[{"type": "web_search"}],

                service_tier="flex",
                text_format=CollisionLookup,
            )
            existing_qid = (resp.output_parsed.existing_qid or "").strip()
            new_qid = (resp.output_parsed.new_qid or "").strip()
            if existing_qid.lower() in {"", "none", "null", "unknown"}:
                existing_qid = None
            if new_qid.lower() in {"", "none", "null", "unknown"}:
                new_qid = None
            if existing_qid and not _QID_RE.match(existing_qid):
                existing_qid = None
            if new_qid and not _QID_RE.match(new_qid):
                new_qid = None
            return existing_qid, new_qid
        except Exception as exc:  # pragma: no cover - network faults
            status = getattr(exc, "status_code", None)
            if status in {408, 429} and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise
    return None, None


async def _process_animals_async(
    db_path: str = DB_FILE,
    client: Any | None = None,
    lookup: Callable[[Any, str, Optional[str], Optional[str]], Optional[str]] | None = None,
    resolve: Callable[
        [
            Any,
            Tuple[str, str, Optional[str], Optional[str]],
            Tuple[str, str, Optional[str], Optional[str]],
            str,
        ],
        Tuple[Optional[str], Optional[str]],
    ]
    | None = None,
    *,
    concurrency: int = 30,
) -> None:
    """Process all animals and update their ``wikidata_qid`` values."""

    if client is None:  # pragma: no cover - exercised only in manual runs
        from openai import OpenAI  # type: ignore

        client = OpenAI(timeout=900.0)

    if lookup is None:
        lookup = lookup_qid
    if resolve is None:
        resolve = resolve_collision

    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    ensure_enrichment_columns(conn)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT art, latin_name, name_de, name_en
        FROM animal
        WHERE klasse < 6
          AND wikidata_qid IS NULL
        ORDER BY zoo_count DESC
        """
    )
    rows = cur.fetchall()

    existing_qids = {
        qid
        for (qid,) in cur.execute(
            "SELECT wikidata_qid FROM animal WHERE wikidata_qid IS NOT NULL"
        )
        if qid
    }
    cols = {row[1] for row in cur.execute("PRAGMA table_info(animal)")}
    clear_cols = tuple(c for c in RESET_COLS if c in cols)

    print(f"{len(rows)} animals to process")

    async for (art, latin, name_de, name_en), qid in lookup_rows(
        rows, client, lookup, concurrency=concurrency
    ):
        print(f"Processing {art} ({latin})")
        if qid and qid not in existing_qids:
            apply_qid_update(
                cur,
                art,
                qid,
                status="llm",
                reset_fields=False,
                clear_cols=clear_cols,
            )
            update_enrichment(cur, art, qid)
            existing_qids.add(qid)
            conn.commit()
            print(f" -> assigned QID {qid}")
        elif qid:
            print(f" -> collision on QID {qid}")
            cur.execute(
                "SELECT art, latin_name, name_de, name_en FROM animal WHERE wikidata_qid=?",
                (qid,),
            )
            existing = cur.fetchone()
            if existing:
                new_info = (art, latin, name_de, name_en)
                pre_existing_qids = set(existing_qids)
                existing_qid, new_qid = await asyncio.to_thread(
                    resolve, client, existing, new_info, qid
                )
                print(
                    f"    resolver returned: existing={existing_qid}, new={new_qid}"
                )
                old_art = existing[0]
                if existing_qid and existing_qid != qid:
                    apply_qid_update(
                        cur,
                        old_art,
                        existing_qid,
                        status="llm",
                        reset_fields=True,
                        clear_cols=clear_cols,
                    )
                    update_enrichment(cur, old_art, existing_qid)
                    existing_qids.discard(qid)
                    existing_qids.add(existing_qid)
                    print(
                        f"    updated {old_art} to {existing_qid} (was {qid})"
                    )
                if new_qid and new_qid not in existing_qids:
                    apply_qid_update(
                        cur,
                        art,
                        new_qid,
                        status="llm",
                        reset_fields=False,
                        clear_cols=clear_cols,
                    )
                    update_enrichment(cur, art, new_qid)
                    existing_qids.add(new_qid)
                    print(f"    assigned {new_qid} to {art}")
                conn.commit()
                if (not existing_qid or existing_qid == qid) and (
                    not new_qid or new_qid in pre_existing_qids
                ):
                    print(
                        "    resolver made no changes (kept existing; new was null/duplicate)"
                    )
            else:
                print(f"    no existing row found for collision {qid}")
        else:
            print(" -> no QID found")

    conn.close()


def process_animals(
    db_path: str = DB_FILE,
    client: Any | None = None,
    lookup: Callable[[Any, str, Optional[str], Optional[str]], Optional[str]] | None = None,
    resolve: Callable[
        [
            Any,
            Tuple[str, str, Optional[str], Optional[str]],
            Tuple[str, str, Optional[str], Optional[str]],
            str,
        ],
        Tuple[Optional[str], Optional[str]],
    ]
    | None = None,
    *,
    concurrency: int = 30,
) -> None:
    """Synchronous wrapper for :func:`_process_animals_async`.

    This allows the function to be called from non-async code while the
    heavy network lookups are executed concurrently.
    """

    try:
        asyncio.run(
            _process_animals_async(
                db_path=db_path,
                client=client,
                lookup=lookup,
                resolve=resolve,
                concurrency=concurrency,
            )
        )
    except RuntimeError:  # event loop already running
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            _process_animals_async(
                db_path=db_path,
                client=client,
                lookup=lookup,
                resolve=resolve,
                concurrency=concurrency,
            )
        )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=30)
    args = parser.parse_args()
    process_animals(concurrency=args.concurrency)
