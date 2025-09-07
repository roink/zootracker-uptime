#!/usr/bin/env python3
"""Generate German & English descriptions for domesticated animals and breeds."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

try:
    from zootier_scraper_sqlite import DB_FILE
except Exception:
    DB_FILE = "zootierliste.db"

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)
except Exception:  # pragma: no cover - optional dependency
    pass

from wiki_descriptions_shared import (
    HTTP_CONCURRENCY,
    OPENAI_CONCURRENCY,
    DOMESTIC_SYSTEM_PROMPT,
    generate_descriptions,
)


async def main(args: argparse.Namespace) -> None:
    await generate_descriptions(args, klasse_condition="= 6", sys_msg=DOMESTIC_SYSTEM_PROMPT)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Write DE/EN descriptions for domesticated animals or breeds from Wikipedia using gpt-5-nano."
    )
    p.add_argument("--db", default=DB_FILE, help="Path to SQLite database (default: %(default)s)")
    p.add_argument("--limit", type=int, default=None, help="Process at most N rows.")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing description_de/description_en.",
    )
    p.add_argument(
        "--http-concurrency",
        type=int,
        default=HTTP_CONCURRENCY,
        help="Parallel HTTP fetches.",
    )
    p.add_argument(
        "--openai-concurrency",
        type=int,
        default=OPENAI_CONCURRENCY,
        help="Parallel OpenAI calls.",
    )
    return p.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        sys.exit(130)
