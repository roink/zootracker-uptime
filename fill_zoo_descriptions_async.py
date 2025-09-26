#!/usr/bin/env python3
"""Fill missing zoo descriptions and metadata using the Gemini API."""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from gemini_utils import (
    GeminiZooClient,
    ZooMetadata,
    ZooRecord,
    get_database_path,
    get_gemini_api_key,
)


DEFAULT_CONCURRENCY = 20
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 30.0


@dataclass(slots=True)
class TargetZoo(ZooMetadata):
    """Zoo metadata plus book-keeping fields loaded for processing."""

    species_count: int


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
    if isinstance(status, int) and (status == 429 or status >= 500):
        return True

    message = str(exc).lower()
    for marker in ("429", "rate limit", "timeout", "temporarily unavailable", "503", "504"):
        if marker in message:
            return True
    return False


def load_target_zoos(db_path: Path, limit: Optional[int]) -> list[TargetZoo]:
    query = """
        SELECT z.zoo_id,
               z.name,
               z.city,
               z.country AS country_id,
               cn.name_en AS country_en,
               z.species_count
        FROM zoo AS z
        LEFT JOIN country_name AS cn ON z.country = cn.id
        WHERE (z.description_en IS NULL OR TRIM(z.description_en) = '')
           OR (z.description_de IS NULL OR TRIM(z.description_de) = '')
        ORDER BY z.species_count DESC, z.zoo_id DESC
    """
    params: tuple[object, ...] = ()
    if limit is not None:
        query += "\n        LIMIT ?"
        params = (limit,)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    targets: list[TargetZoo] = []
    for row in rows:
        targets.append(
            TargetZoo(
                zoo_id=row["zoo_id"],
                name=row["name"],
                city=row["city"],
                country_id=row["country_id"],
                country_en=row["country_en"] or "",
                species_count=row["species_count"],
            )
        )
    return targets


async def gather_zoo_details(
    client: GeminiZooClient,
    semaphore: asyncio.Semaphore,
    zoo: TargetZoo,
) -> tuple[int, Optional[ZooRecord]]:
    prompt = zoo.to_prompt()
    try:
        async with semaphore:
            research_output = await call_with_backoff(client.research_zoo_async, prompt)
            structured = await call_with_backoff(
                client.structure_response_async, research_output
            )
    except Exception as exc:  # pragma: no cover - network errors are non-deterministic
        logging.exception("Gemini call failed for zoo_id %s: %s", zoo.zoo_id, exc)
        return zoo.zoo_id, None

    return zoo.zoo_id, structured


def sanitize_description(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def parse_visitors(value: Optional[int | str]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else None
    except ValueError:
        return None


def ensure_unique(
    conn: sqlite3.Connection, column: str, value: str, current_zoo_id: int
) -> bool:
    row = conn.execute(
        f"SELECT zoo_id FROM zoo WHERE LOWER({column}) = LOWER(?) AND zoo_id != ?", (value, current_zoo_id)
    ).fetchone()
    return row is None


def update_database(
    db_path: Path,
    zoo_id: int,
    record: ZooRecord,
) -> None:
    description_en = sanitize_description(record.description_en)
    description_de = sanitize_description(record.description_de)
    visitors = parse_visitors(record.visitors)
    website = str(record.website) if record.website else None
    wikipedia_en = str(record.wikipedia_en) if record.wikipedia_en else None
    wikipedia_de = str(record.wikipedia_de) if record.wikipedia_de else None

    updates: dict[str, object] = {}
    if description_en:
        updates["description_en"] = description_en
    if description_de:
        updates["description_de"] = description_de
    if visitors is not None:
        updates["number_visitors"] = visitors

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if website and ensure_unique(conn, "official_website", website, zoo_id):
            updates["official_website"] = website
        elif website:
            logging.warning(
                "official_website collision for zoo_id %s with value %s", zoo_id, website
            )
        if wikipedia_en and ensure_unique(conn, "wikipedia_en", wikipedia_en, zoo_id):
            updates["wikipedia_en"] = wikipedia_en
        elif wikipedia_en:
            logging.warning(
                "wikipedia_en collision for zoo_id %s with value %s", zoo_id, wikipedia_en
            )
        if wikipedia_de and ensure_unique(conn, "wikipedia_de", wikipedia_de, zoo_id):
            updates["wikipedia_de"] = wikipedia_de
        elif wikipedia_de:
            logging.warning(
                "wikipedia_de collision for zoo_id %s with value %s", zoo_id, wikipedia_de
            )

        if not updates:
            logging.info("No updates produced for zoo_id %s", zoo_id)
            return

        updates["source"] = "gemini"
        placeholders = ", ".join(f"{col} = ?" for col in updates.keys())
        params = list(updates.values()) + [zoo_id]
        conn.execute(f"UPDATE zoo SET {placeholders} WHERE zoo_id = ?", params)
        conn.commit()

    logging.info(
        "Updated zoo_id %s with fields: %s", zoo_id, ", ".join(sorted(updates.keys()))
    )


async def process_zoos(
    db_path: Path,
    client: GeminiZooClient,
    zoos: Iterable[TargetZoo],
    concurrency: int,
) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        asyncio.create_task(gather_zoo_details(client, semaphore, zoo)) for zoo in zoos
    ]
    for coro in asyncio.as_completed(tasks):
        zoo_id, record = await coro
        if record is None:
            continue
        await asyncio.to_thread(update_database, db_path, zoo_id, record)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill missing zoo descriptions and metadata via Gemini.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQLite database (default: taken from .env)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit processing to the first N zoos.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="Maximum number of concurrent Gemini requests (default: %(default)s)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    db_path = args.db or get_database_path()
    api_key = get_gemini_api_key()
    target_zoos = load_target_zoos(Path(db_path), args.limit)
    if not target_zoos:
        logging.info("No zoos require updates.")
        return

    logging.info("Processing %s zoos with concurrency=%s", len(target_zoos), args.concurrency)

    client = GeminiZooClient(api_key=api_key)
    await process_zoos(Path(db_path), client, target_zoos, min(args.concurrency, DEFAULT_CONCURRENCY))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
