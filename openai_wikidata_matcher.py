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

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from zootier_scraper_sqlite import DB_FILE, ensure_db_schema

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


@dataclass
class _ResponseContent:
    """Minimal structure of the content field in the Responses API output."""

    json: dict[str, Any]


@dataclass
class _ResponseOutput:
    content: list[_ResponseContent]


@dataclass
class _Response:
    output: list[_ResponseOutput]


_QID_RE = re.compile(r"^Q\d+$")


def _extract_qid(resp: _Response) -> Optional[str]:
    """Extract the ``wikidata_qid`` value from a Responses API payload."""

    try:
        data = resp.output[0].content[0].json
    except (AttributeError, IndexError, KeyError):
        return None
    qid = data.get("wikidata_qid")
    if qid is None:
        return None
    qid_str = str(qid).strip()
    if qid_str.lower() in {"", "none", "null", "unknown"}:
        return None
    if not _QID_RE.match(qid_str):
        return None
    return qid_str


def lookup_qid(client: Any, latin: str, name_de: Optional[str], name_en: Optional[str]) -> Optional[str]:
    """Query the OpenAI API and return a Wikidata QID or ``None``.

    Parameters
    ----------
    client:
        An object exposing ``responses.create`` compatible with the OpenAI
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
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "wikidata_lookup",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "wikidata_qid": {"type": ["string", "null"]}
                },
                "required": ["wikidata_qid"],
                "additionalProperties": False,
            },
        },
    }
    client_opt = (
        client.with_options(timeout=900.0)
        if hasattr(client, "with_options")
        else client
    )
    for attempt in range(3):
        try:
            resp = client_opt.responses.create(
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
                service_tier="flex",
                response_format=schema,
            )
            return _extract_qid(resp)
        except Exception as exc:  # pragma: no cover - network faults
            status = getattr(exc, "status_code", None)
            if status in {408, 429} and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise
    return None


def process_animals(
    db_path: str = DB_FILE,
    client: Any | None = None,
    lookup: Callable[[Any, str, Optional[str], Optional[str]], Optional[str]] | None = None,
) -> None:
    """Process all animals and update their ``wikidata_qid`` values."""

    if client is None:  # pragma: no cover - exercised only in manual runs
        from openai import OpenAI  # type: ignore

        client = OpenAI(timeout=900.0)

    if lookup is None:
        lookup = lookup_qid

    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
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

    for art, latin, name_de, name_en in rows:
        qid = lookup(client, latin, name_de, name_en)
        if qid and qid not in existing_qids:
            cur.execute(
                "UPDATE animal SET wikidata_qid=?, wikidata_match_status=?, wikidata_match_method=? WHERE art=?",
                (qid, "llm", "gpt-5-mini", art),
            )
            existing_qids.add(qid)
            conn.commit()
        elif qid:
            print(f"collision for {art}: {qid}")

    conn.close()


if __name__ == "__main__":  # pragma: no cover - manual invocation
    process_animals()
