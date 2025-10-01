#!/usr/bin/env python3
"""Fill missing animal descriptions and metadata using the Gemini API."""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import re
import sqlite3
import sys
from urllib.parse import urlparse, urlunparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from gemini_utils import (
    AnimalMetadata,
    AnimalRecord,
    GeminiAnimalClient,
    get_database_path,
    get_gemini_api_key,
)

DEFAULT_CONCURRENCY = 20
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 30.0

REQUIRED_COLUMNS: dict[str, str] = {
    "source": "TEXT",
}


@dataclass
class TargetAnimal(AnimalMetadata):
    """Animal metadata plus queue ordering details."""

    zoo_count: int


async def call_with_backoff(func, *args, **kwargs):
    """Execute *func* with exponential backoff for transient failures."""

    delay = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - network errors are non-deterministic
            if attempt == MAX_RETRIES or not is_retryable_exception(exc):
                raise
            jitter = random.uniform(0, delay / 2)
            await asyncio.sleep(min(MAX_BACKOFF, delay) + jitter)
            delay *= 2


def is_retryable_exception(exc: Exception) -> bool:
    """Return True if the exception looks like a transient API failure."""

    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if isinstance(status, int) and (status in (408, 429, 500, 502, 503, 504) or status >= 500):
        return True

    message = str(exc).lower()
    for marker in (
        "408",
        "429",
        "rate limit",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "502",
        "503",
        "504",
        "deadline",
        "connection reset",
    ):
        if marker in message:
            return True
    return False


def load_target_animals(db_path: Path, limit: Optional[int]) -> list[TargetAnimal]:
    query = """
        SELECT a.art,
               a.latin_name,
               a.name_de,
               a.name_en,
               a.klasse,
               kn.name_de AS klasse_de,
               kn.name_en AS klasse_en,
               oname.name_de AS ordnung_de,
               oname.name_en AS ordnung_en,
               fn.name_de AS familie_de,
               fn.name_en AS familie_en,
               a.zoo_count
        FROM animal AS a
        LEFT JOIN klasse_name AS kn ON a.klasse = kn.klasse
        LEFT JOIN ordnung_name AS oname ON a.ordnung = oname.ordnung
        LEFT JOIN familie_name AS fn ON a.familie = fn.familie
        WHERE ((a.description_en IS NULL OR TRIM(a.description_en) = '')
           OR (a.description_de IS NULL OR TRIM(a.description_de) = ''))
          AND a.zoo_count > 0
          AND a.klasse <= 6
        ORDER BY a.zoo_count DESC, a.art ASC
    """
    params: tuple[object, ...] = ()
    if limit is not None:
        query += "\n        LIMIT ?"
        params = (limit,)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    targets: list[TargetAnimal] = []
    for row in rows:
        targets.append(
            TargetAnimal(
                art=row["art"],
                latin_name=row["latin_name"],
                name_de=row["name_de"],
                name_en=row["name_en"],
                klasse_de=row["klasse_de"],
                klasse_en=row["klasse_en"],
                ordnung_de=row["ordnung_de"],
                ordnung_en=row["ordnung_en"],
                familie_de=row["familie_de"],
                familie_en=row["familie_en"],
                zoo_count=row["zoo_count"],
                is_domestic=(row["klasse"] == 6 if row["klasse"] is not None else False),
            )
        )
    return targets


def ensure_columns_exist(db_path: Path) -> None:
    """Add missing columns required by this script."""

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = {
            row["name"].lower()
            for row in conn.execute("PRAGMA table_info(animal)").fetchall()
        }

        for column, definition in REQUIRED_COLUMNS.items():
            if column.lower() in existing:
                continue

            logging.info("Adding missing column %s to animal table", column)
            conn.execute(f"ALTER TABLE animal ADD COLUMN {column} {definition}")
        conn.commit()


_DESCRIPTION_MARKDOWN_PATTERN = re.compile(r"[*_#]")
_MULTISPACE_PATTERN = re.compile(r"\s+")


def sanitize_description(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    cleaned = _DESCRIPTION_MARKDOWN_PATTERN.sub("", cleaned)
    cleaned = _MULTISPACE_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def sanitize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def is_empty(value: Optional[str]) -> bool:
    return value is None or not str(value).strip()


def _normalize_wikipedia_url(url: Optional[str]) -> Optional[str]:
    """Normalise Wikipedia URLs to a canonical form."""

    if not url:
        return None

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url

    if not parsed.netloc:
        return url

    host = parsed.netloc.lower()
    if "wikipedia.org" not in host:
        return url

    return urlunparse(("https", host, parsed.path, "", "", ""))


def ensure_unique(conn: sqlite3.Connection, column: str, value: str, current_art: str) -> bool:
    row = conn.execute(
        f"SELECT art FROM animal WHERE LOWER({column}) = LOWER(?) AND art != ?",
        (value, current_art),
    ).fetchone()
    return row is None


async def gather_animal_details(
    client: GeminiAnimalClient,
    semaphore: asyncio.Semaphore,
    animal: TargetAnimal,
) -> tuple[TargetAnimal, Optional[AnimalRecord]]:
    prompt = animal.to_prompt()
    try:
        async with semaphore:
            research_output = await call_with_backoff(client.research_animal_async, prompt)
            structured = await call_with_backoff(
                client.structure_response_async, research_output
            )
    except Exception as exc:  # pragma: no cover - network errors are non-deterministic
        logging.exception("Gemini call failed for art %s: %s", animal.art, exc)
        return animal, None

    return animal, structured


def update_database(
    db_path: Path,
    animal: TargetAnimal,
    record: AnimalRecord,
) -> None:
    art = animal.art
    description_en = sanitize_description(record.description_en)
    description_de = sanitize_description(record.description_de)
    wikipedia_en = _normalize_wikipedia_url(sanitize_text(record.wikipedia_en))
    wikipedia_de = _normalize_wikipedia_url(sanitize_text(record.wikipedia_de))
    taxon_rank = sanitize_text(record.taxon_rank) if not animal.is_domestic else None
    iucn_status = sanitize_text(record.iucn_conservation_status)
    if animal.is_domestic:
        iucn_status = None

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            """
            SELECT description_en,
                   description_de,
                   wikipedia_en,
                   wikipedia_de,
                   taxon_rank,
                   iucn_conservation_status,
                   source,
                   klasse
            FROM animal
            WHERE art = ?
            """,
            (art,),
        ).fetchone()
        if existing is None:
            logging.warning("Animal with art %s not found during update", art)
            return

        existing_klasse = existing["klasse"]

        updates: dict[str, object] = {}
        if description_en and is_empty(existing["description_en"]):
            updates["description_en"] = description_en
        if description_de and is_empty(existing["description_de"]):
            updates["description_de"] = description_de
        if taxon_rank and (existing_klasse != 6) and is_empty(existing["taxon_rank"]):
            updates["taxon_rank"] = taxon_rank
        if iucn_status and (existing_klasse != 6) and is_empty(existing["iucn_conservation_status"]):
            updates["iucn_conservation_status"] = iucn_status

        if wikipedia_en and is_empty(existing["wikipedia_en"]):
            if ensure_unique(conn, "wikipedia_en", wikipedia_en, art):
                updates["wikipedia_en"] = wikipedia_en
            else:
                logging.warning(
                    "wikipedia_en collision for art %s with value %s", art, wikipedia_en
                )
        if wikipedia_de and is_empty(existing["wikipedia_de"]):
            if ensure_unique(conn, "wikipedia_de", wikipedia_de, art):
                updates["wikipedia_de"] = wikipedia_de
            else:
                logging.warning(
                    "wikipedia_de collision for art %s with value %s", art, wikipedia_de
                )

        if not updates:
            logging.info("No updates produced for art %s", art)
            return

        updates["source"] = "gemini"

        placeholders = ", ".join(f"{col} = ?" for col in updates.keys())
        params = list(updates.values()) + [art]
        conn.execute(f"UPDATE animal SET {placeholders} WHERE art = ?", params)
        conn.commit()

    logging.info(
        "Updated art %s with fields: %s", art, ", ".join(sorted(updates.keys()))
    )


async def process_animals(
    db_path: Path,
    client: GeminiAnimalClient,
    animals: Iterable[TargetAnimal],
    concurrency: int,
) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        asyncio.create_task(gather_animal_details(client, semaphore, animal))
        for animal in animals
    ]
    for coro in asyncio.as_completed(tasks):
        animal, record = await coro
        if record is None:
            continue
        await asyncio.to_thread(update_database, db_path, animal, record)


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill missing animal descriptions and metadata via Gemini.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQLite database (default: taken from .env)",
    )
    parser.add_argument(
        "--concurrency",
        type=positive_int,
        default=DEFAULT_CONCURRENCY,
        help="Maximum number of concurrent Gemini requests (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help=(
            "Limit processing to the first N animals sorted by zoo count. "
            "For example, --limit 100 restricts processing to the top 100 animals."
        ),
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    db_path = Path(args.db or get_database_path())
    ensure_columns_exist(db_path)
    api_key = get_gemini_api_key()
    target_animals = load_target_animals(db_path, args.limit)
    if not target_animals:
        logging.info("No animals require updates.")
        return

    logging.info(
        "Processing %s animals with concurrency=%s", len(target_animals), args.concurrency
    )

    client = GeminiAnimalClient(api_key)
    await process_animals(
        db_path,
        client,
        target_animals,
        args.concurrency,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
