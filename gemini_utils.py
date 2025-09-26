"""Utility helpers for gathering zoo information with the Google Gemini API."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, HttpUrl, field_validator
from urllib.parse import urlparse

ENV_FILE_PATH = Path(".env")
RESEARCH_MODEL = "gemini-flash-latest"
STRUCTURED_MODEL = "gemini-flash-lite-latest"

PROMPT_TEMPLATE = """Please search for information on this zoo or animal park.
Country: {country_en}
City: {city}
Name: {name}

Please write an english description of about 4-6 sentences about this zoo, as well as a german description.
This is meant for a website that offers users information about zoos and animals.
Please stay factual, don't use the marketing language that you might find on the zoos homepage.
Please write an engaging description and mention anything that is unique or special about the zoo.
Please search for information in english as well as using the language of the country of the zoo.

Please try to find information about the number of visitors the zoo has per year.
Find the URL of the official homepage if it exists.
Find the URL of the wikipedia page if it exists.
Find the URL of the german wikipedia page if it exists.
Please look at the website and wikipedia websites carefully, to make sure they belong to this exact zoo.

Answer in this structure:
description_en:
description_de:
visitors:
website:
wikipedia_en:
wikipedia_de:
"""


class ZooRecord(BaseModel):
    """Structured representation expected from the second Gemini call."""

    description_en: str
    description_de: str
    visitors: Optional[int] = None
    website: Optional[HttpUrl] = None
    wikipedia_en: Optional[HttpUrl] = None
    wikipedia_de: Optional[HttpUrl] = None

    @field_validator("website", "wikipedia_en", "wikipedia_de", mode="before")
    @classmethod
    def _normalise_url(cls, value: Optional[str]) -> Optional[str]:
        """Accept bare domains by prepending https:// before validation."""

        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        parsed = urlparse(text)
        if not parsed.scheme:
            text = f"https://{text}"
            parsed = urlparse(text)

        # urlparse treats values like "https://example" as having the scheme but
        # no network location. Reject such cases by returning the cleaned string
        # so HttpUrl validation can still fail, ensuring data quality.
        if not parsed.netloc:
            return text

        return text


@dataclass
class ZooMetadata:
    """Minimal zoo information loaded from the SQLite database."""

    zoo_id: int
    name: str
    city: str
    country_id: Optional[int]
    country_en: str

    def to_prompt(self) -> str:
        return PROMPT_TEMPLATE.format(
            country_en=self.country_en or "",
            city=self.city,
            name=self.name,
        )


_ENV_CACHE: Dict[str, str] | None = None


def read_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE .env file."""

    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_env() -> Dict[str, str]:
    """Load the cached environment variables from the local .env file."""

    global _ENV_CACHE
    if _ENV_CACHE is None:
        if not ENV_FILE_PATH.exists():
            raise FileNotFoundError(
                "Expected .env file next to the scripts but none was found."
            )
        _ENV_CACHE = read_env_file(ENV_FILE_PATH)
    return _ENV_CACHE


def get_gemini_api_key() -> str:
    """Return the Gemini API key from the environment or the .env file."""

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    env_values = load_env()
    api_key = env_values.get("GEMINI_API_KEY")
    if api_key:
        return api_key

    raise RuntimeError(
        "GEMINI_API_KEY is missing. Please add it to the environment or the .env file."
    )


def get_database_path() -> Path:
    """Read the SQLite database path from the .env file."""

    env_values = load_env()
    db_file = env_values.get("DB_FILE")
    if not db_file:
        raise RuntimeError("DB_FILE is missing in the .env file.")

    return Path(db_file)


def fetch_zoo_metadata(zoo_id: int, db_path: Path | str | None = None) -> ZooMetadata:
    """Fetch the minimal zoo metadata required for Gemini prompts."""

    if db_path is None:
        db_path = get_database_path()
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT z.zoo_id,
                   z.name,
                   z.city,
                   z.country AS country_id,
                   cn.name_en AS country_en
            FROM zoo AS z
            LEFT JOIN country_name AS cn ON z.country = cn.id
            WHERE z.zoo_id = ?
            """,
            (zoo_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"No zoo with zoo_id={zoo_id} exists in {db_path}")

    return ZooMetadata(
        zoo_id=row["zoo_id"],
        name=row["name"],
        city=row["city"],
        country_id=row["country_id"],
        country_en=row["country_en"] or "",
    )


class GeminiZooClient:
    """Wrapper around the google-genai client for the two required calls."""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def research_zoo(self, prompt: str) -> str:
        """Run the research-oriented Gemini call and return the raw text output."""

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            )
        ]
        tools = [types.Tool(googleSearch=types.GoogleSearch())]
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
            tools=tools,
        )

        chunks = []
        for chunk in self.client.models.generate_content_stream(
            model=RESEARCH_MODEL,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                chunks.append(chunk.text)
        return "".join(chunks).strip()

    def structure_response(self, partially_structured_text: str) -> ZooRecord:
        """Convert the research output into a structured JSON payload."""

        prompt = (
            "Extract the following text into the requested fields. "
            "The visitors field is supposed to contain the yearly number of visitors. "
            "Remove formatiing from the description fields, other than usual punctuation."
            "If a field is not present, leave it null instead of guessing.\n\n"
            f"{partially_structured_text}"
        )
        response = self.client.models.generate_content(
            model=STRUCTURED_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ZooRecord,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return ZooRecord.model_validate_json(response.text)

    async def research_zoo_async(self, prompt: str) -> str:
        """Async wrapper around :meth:`research_zoo`."""

        return await asyncio.to_thread(self.research_zoo, prompt)

    async def structure_response_async(self, partially_structured_text: str) -> ZooRecord:
        """Async wrapper around :meth:`structure_response`."""

        return await asyncio.to_thread(self.structure_response, partially_structured_text)

