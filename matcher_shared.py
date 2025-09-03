"""Shared helpers for Wikidata matcher scripts."""

from __future__ import annotations

import asyncio
import random
import sqlite3
from typing import Any, AsyncIterator, Callable, Optional, TypeVar

import httpx

from zootierliste_enrich_async import fetch_details, fetch_wikipedia, HEADERS

try:  # pragma: no cover - optional dependency in tests
    from openai import (
        APIConnectionError,
        APIStatusError,
        RateLimitError,
        APITimeoutError,
    )  # type: ignore
except Exception:  # pragma: no cover - library missing
    class APIConnectionError(Exception):  # type: ignore
        """Fallback ``openai`` exception."""

    class APIStatusError(Exception):  # type: ignore
        """Fallback ``openai`` exception with ``status_code`` attribute."""

        status_code: int | None = None

    class RateLimitError(Exception):  # type: ignore
        """Fallback ``openai`` exception."""

    class APITimeoutError(Exception):  # type: ignore
        """Fallback ``openai`` exception."""

T = TypeVar("T")


RESET_COLS = [
    "wikidata_match_score",
    "wikidata_review_json",
    "wikidata_id",
    "taxon_rank",
    "parent_taxon",
    "wikipedia_en",
    "wikipedia_de",
    "iucn_conservation_status",
]


def ensure_enrichment_columns(conn: sqlite3.Connection) -> None:
    """Add enrichment columns to the ``animal`` table if they do not exist."""

    cur = conn.cursor()
    for col in (
        "taxon_rank TEXT",
        "parent_taxon TEXT",
        "wikipedia_en TEXT",
        "wikipedia_de TEXT",
        "iucn_conservation_status TEXT",
    ):
        try:
            cur.execute(f"ALTER TABLE animal ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    conn.commit()


async def _fetch_all_async(qid: str) -> dict[str, str]:
    async with httpx.AsyncClient(http2=True, headers=HEADERS, timeout=30) as client:
        results = await asyncio.gather(
            fetch_wikipedia(client, qid, "en"),
            fetch_wikipedia(client, qid, "de"),
            fetch_details(client, qid),
        )
    merged: dict[str, str] = {}
    for res in results:
        merged.update(res)
    return merged


def fetch_wikidata_enrichment(qid: str) -> dict[str, str]:
    """Fetch Wikipedia links and basic taxonomic data for *qid*."""

    try:
        return asyncio.run(_fetch_all_async(qid))
    except RuntimeError:  # event loop already running
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_fetch_all_async(qid))


def apply_qid_update(
    cur: sqlite3.Cursor,
    art: str,
    qid: Optional[str],
    *,
    status: str,
    reset_fields: bool,
    clear_cols: tuple[str, ...],
) -> None:
    """Update a row with a new QID and optionally reset metadata."""

    set_bits = ["wikidata_qid=?", "wikidata_match_status=?", "wikidata_match_method=?"]
    params: list[object] = [qid, status, "gpt-5-mini"]
    if reset_fields:
        set_bits += [f"{c}=NULL" for c in clear_cols]
    cur.execute(
        f"UPDATE animal SET {', '.join(set_bits)} WHERE art=?",
        (*params, art),
    )


async def lookup_rows(
    rows: list[tuple[str, str, Optional[str], Optional[str]]],
    client: Any,
    lookup: Callable[[Any, str, Optional[str], Optional[str]], T],
    *,
    concurrency: int = 30,
    fail_value: Optional[T] = None,
) -> AsyncIterator[tuple[tuple[str, str, Optional[str], Optional[str]], Optional[T]]]:
    """Yield lookup results for *rows* as they become available."""

    sem = asyncio.Semaphore(concurrency)

    async def run(
        row: tuple[str, str, Optional[str], Optional[str]]
    ) -> tuple[tuple[str, str, Optional[str], Optional[str]], Optional[T]]:
        art, latin, name_de, name_en = row
        for attempt in range(4):
            try:
                async with sem:
                    result = await asyncio.to_thread(lookup, client, latin, name_de, name_en)
                return row, result
            except (
                APIConnectionError,
                RateLimitError,
                APITimeoutError,
                APIStatusError,
            ) as exc:  # pragma: no cover - network faults
                status = getattr(exc, "status_code", None)
                retryable = (
                    isinstance(
                        exc, (APIConnectionError, RateLimitError, APITimeoutError)
                    )
                    or status in {408, 429}
                    or (status is not None and status >= 500)
                )
                if not retryable or attempt == 3:
                    print(f"Lookup failed for {latin}: {exc}")
                    return row, fail_value
                sleep = min(60, 1 * 2**attempt) + random.uniform(0, 1)
                print(
                    f"Retrying {latin} in {sleep:.1f}s (attempt {attempt+1}/4)"
                )
                await asyncio.sleep(sleep)
        return row, fail_value

    tasks = [asyncio.create_task(run(row)) for row in rows]
    for task in asyncio.as_completed(tasks):
        yield await task

