#!/usr/bin/env python3
"""Populate Gemini-derived coordinates for zoos missing enriched data."""

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
    GeminiCoordinateClient,
    ZooCoordinateRecord,
    ZooMetadata,
    get_database_path,
    get_gemini_api_key,
)

DEFAULT_CONCURRENCY = 20
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 30.0

REQUIRED_COLUMNS: dict[str, str] = {
    "latitude_gemini": "REAL",
    "longitude_gemini": "REAL",
}


@dataclass(slots=True)
class TargetZoo(ZooMetadata):
    """Zoo metadata together with sort order fields."""

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


def ensure_columns_exist(db_path: Path) -> None:
    """Ensure the Gemini coordinate columns exist on the zoo table."""

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = {
            row["name"].lower()
            for row in conn.execute("PRAGMA table_info(zoo)").fetchall()
        }

        for column, definition in REQUIRED_COLUMNS.items():
            if column.lower() in existing:
                continue
            logging.info("Adding missing column %s to zoo table", column)
            conn.execute(f"ALTER TABLE zoo ADD COLUMN {column} {definition}")
        conn.commit()


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
        WHERE z.latitude_gemini IS NULL OR z.longitude_gemini IS NULL
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
                species_count=row["species_count"] or 0,
            )
        )
    return targets


async def gather_coordinates(
    client: GeminiCoordinateClient,
    semaphore: asyncio.Semaphore,
    zoo: TargetZoo,
) -> tuple[int, Optional[ZooCoordinateRecord]]:
    prompt = zoo.to_coordinate_prompt()
    try:
        async with semaphore:
            research_output = await call_with_backoff(
                client.research_coordinates_async, prompt
            )
            structured = await call_with_backoff(
                client.structure_response_async, research_output
            )
    except Exception as exc:  # pragma: no cover - network errors are non-deterministic
        logging.exception("Gemini call failed for zoo_id %s: %s", zoo.zoo_id, exc)
        return zoo.zoo_id, None

    return zoo.zoo_id, structured


def validate_coordinates(record: ZooCoordinateRecord) -> tuple[Optional[float], Optional[float]]:
    latitude = record.latitude
    longitude = record.longitude

    if latitude is None or longitude is None:
        return None, None

    if not (-90 <= latitude <= 90):
        logging.warning("Discarding latitude %.6f for being out of range", latitude)
        return None, None
    if not (-180 <= longitude <= 180):
        logging.warning("Discarding longitude %.6f for being out of range", longitude)
        return None, None

    return latitude, longitude


def update_database(db_path: Path, zoo_id: int, record: ZooCoordinateRecord) -> None:
    latitude, longitude = validate_coordinates(record)
    if latitude is None or longitude is None:
        logging.info("No valid coordinates returned for zoo_id %s", zoo_id)
        return

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE zoo SET latitude_gemini = ?, longitude_gemini = ? WHERE zoo_id = ?",
            (latitude, longitude, zoo_id),
        )
        conn.commit()

    logging.info(
        "Updated coordinates for zoo_id %s: latitude=%.6f, longitude=%.6f",
        zoo_id,
        latitude,
        longitude,
    )
    if record.source:
        logging.info("Source for zoo_id %s coordinates: %s", zoo_id, record.source)


async def process_zoos(
    db_path: Path,
    client: GeminiCoordinateClient,
    zoos: Iterable[TargetZoo],
    concurrency: int,
) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        asyncio.create_task(gather_coordinates(client, semaphore, zoo)) for zoo in zoos
    ]
    for coro in asyncio.as_completed(tasks):
        zoo_id, record = await coro
        if record is None:
            continue
        await asyncio.to_thread(update_database, db_path, zoo_id, record)


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Gemini-enriched coordinates for zoos lacking them.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQLite database (default: taken from .env)",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help=(
            "Limit processing to the first N zoos sorted by species count. "
            "For example, --limit 100 restricts processing to the top 100 zoos."
        ),
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

    db_path = Path(args.db or get_database_path())
    ensure_columns_exist(db_path)

    api_key = get_gemini_api_key()
    target_zoos = load_target_zoos(db_path, args.limit)
    if not target_zoos:
        logging.info("No zoos require coordinate updates.")
        return

    concurrency = max(1, min(args.concurrency, DEFAULT_CONCURRENCY))
    logging.info(
        "Processing %s zoos with concurrency=%s", len(target_zoos), concurrency
    )

    client = GeminiCoordinateClient(api_key=api_key)
    await process_zoos(db_path, client, target_zoos, concurrency)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
