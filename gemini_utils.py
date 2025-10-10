"""Utility helpers for gathering zoo information with the Google Gemini API."""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, Literal, Optional, Type, cast
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

COORDINATE_PROMPT_TEMPLATE = """You are a research assistant that specialises in geocoding.
Country: {country_en}
City: {city}
Zoo name: {name}

Search for the precise location of this zoo and report its geographic coordinates.
Provide latitude and longitude in decimal degrees using the WGS84 coordinate system.
Always use a dot as the decimal separator (for example, 47.1234) and include the
labels "Latitude:" and "Longitude:" next to the values in your response.
"""

ANIMAL_PROMPT_TEMPLATE = """Research the following animal to provide factual information for a zoo information website.

Latin name: {latin_name}
German name: {name_de}
English name: {name_en}
Class (English): {klasse_en}
Order (English): {ordnung_en}
Family (English): {familie_en}

{additional_guidance}

Please write a concise but engaging description in English (4-6 sentences) and in German (4-6 sentences).
Mention notable physical traits, natural habitat, and interesting behavioural facts that are relevant to zoo visitors.
If this is a subspecies explain how this taxon relates to the species in the descriptions.

Search sources in both English and German when possible.
If you cannot find information for a field, clearly state that it is unknown instead of guessing.

Answer in this structure:
- description_en
- description_de
- wikipedia_en (URL if available)
- wikipedia_de (URL if available)
- taxon_rank (must be either "species", "subspecies", or leave blank if unknown)
- iucn_conservation_status (one of "Critically Endangered", "Data Deficient", "Endangered status", "Least Concern", "Near Threatened", "Vulnerable", "extinct in the wild", or leave blank if unknown)
"""

DEFAULT_STRUCTURE_INSTRUCTIONS = (
    "Extract the relevant information from the text and respond with JSON that matches the "
    "provided schema exactly. Return only JSON. Use null for values that are missing or "
    "cannot be confirmed."
)


_DESCRIPTION_MARKERS_RE = re.compile(r"[*_#]")


def _clean_description_text(value: Optional[str]) -> str:
    """Normalise Gemini description fields for consistent downstream use."""

    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = _DESCRIPTION_MARKERS_RE.sub("", text)
    return " ".join(text.split())


def _normalise_url(value: Optional[str]) -> Optional[str]:
    """Normalise user-provided URLs for validation."""

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    parsed = urlparse(text)
    if not parsed.scheme:
        text = f"https://{text}"
        parsed = urlparse(text)

    if not parsed.netloc:
        return text

    return text


class ZooRecord(BaseModel):
    """Structured representation expected from the second Gemini call."""

    description_en: str
    description_de: str
    visitors: Optional[int] = None
    website: Optional[HttpUrl] = None
    wikipedia_en: Optional[HttpUrl] = None
    wikipedia_de: Optional[HttpUrl] = None

    @field_validator("description_en", "description_de", mode="before")
    @classmethod
    def _clean_descriptions(cls, value: str) -> str:
        """Strip extra whitespace and markdown formatting from descriptions."""

        return _clean_description_text(value)

    @field_validator("website", "wikipedia_en", "wikipedia_de", mode="before")
    @classmethod
    def _normalise_url(cls, value: Optional[str]) -> Optional[str]:
        """Accept bare domains by prepending https:// before validation."""

        return _normalise_url(value)


class ZooCoordinateRecord(BaseModel):
    """Structured Gemini response for zoo coordinate lookups."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None


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

    def to_coordinate_prompt(self) -> str:
        return COORDINATE_PROMPT_TEMPLATE.format(
            country_en=self.country_en or "",
            city=self.city,
            name=self.name,
        )


@dataclass(kw_only=True)
class AnimalMetadata:
    """Minimal animal information used to build Gemini prompts."""

    art: str
    latin_name: str | None
    name_de: str | None
    name_en: str | None
    klasse_de: str | None
    klasse_en: str | None
    ordnung_de: str | None
    ordnung_en: str | None
    familie_de: str | None
    familie_en: str | None
    is_domestic: bool = False

    def _format_value(self, value: Optional[str]) -> str:
        return value or "Unknown"

    def to_prompt(self) -> str:
        additional_guidance = ""
        if self.is_domestic:
            additional_parts = [
                "Make it clear in the descriptions that the animal is a domesticated form or specific breed of a wild ancestor.",
                "Leave the taxon_rank field blank for domesticated animals.",
            ]
            additional_guidance = "\n".join(additional_parts)

        return ANIMAL_PROMPT_TEMPLATE.format(
            latin_name=self._format_value(self.latin_name),
            name_de=self._format_value(self.name_de),
            name_en=self._format_value(self.name_en),
            klasse_en=self._format_value(self.klasse_en),
            ordnung_en=self._format_value(self.ordnung_en),
            familie_en=self._format_value(self.familie_en),
            additional_guidance=additional_guidance,
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


def fetch_animal_metadata(art: str, db_path: Path | str | None = None) -> AnimalMetadata:
    """Fetch animal metadata along with taxonomic context for prompts."""

    if db_path is None:
        db_path = get_database_path()
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
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
                   fn.name_en AS familie_en
            FROM animal AS a
            LEFT JOIN klasse_name AS kn ON a.klasse = kn.klasse
            LEFT JOIN ordnung_name AS oname ON a.ordnung = oname.ordnung
            LEFT JOIN familie_name AS fn ON a.familie = fn.familie
            WHERE a.art = ?
            """,
            (art,),
        ).fetchone()

    if row is None:
        raise ValueError(f"No animal with art={art} exists in {db_path}")

    return AnimalMetadata(
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
        is_domestic=(row["klasse"] == 6 if row["klasse"] is not None else False),
    )


class AnimalRecord(BaseModel):
    """Structured Gemini response containing animal specific data."""

    description_en: str
    description_de: str
    wikipedia_en: Optional[HttpUrl] = None
    wikipedia_de: Optional[HttpUrl] = None
    taxon_rank: Optional[Literal["species", "subspecies"]] = None
    iucn_conservation_status: Optional[
        Literal[
            "Critically Endangered",
            "Data Deficient",
            "Endangered status",
            "Least Concern",
            "Near Threatened",
            "Vulnerable",
            "extinct in the wild",
        ]
    ] = None

    _TAXON_RANK_MAP: ClassVar[dict[str, str]] = {
        "species": "species",
        "sp.": "species",
        "sp": "species",
        "subspecies": "subspecies",
        "sub species": "subspecies",
        "ssp": "subspecies",
    }
    _IUCN_STATUS_MAP: ClassVar[dict[str, str]] = {
        "critically endangered": "Critically Endangered",
        "cr": "Critically Endangered",
        "data deficient": "Data Deficient",
        "dd": "Data Deficient",
        "endangered status": "Endangered status",
        "endangered": "Endangered status",
        "en": "Endangered status",
        "least concern": "Least Concern",
        "lc": "Least Concern",
        "near threatened": "Near Threatened",
        "nt": "Near Threatened",
        "vulnerable": "Vulnerable",
        "vu": "Vulnerable",
        "extinct in the wild": "extinct in the wild",
        "ew": "extinct in the wild",
    }

    @field_validator("description_en", "description_de", mode="before")
    @classmethod
    def _clean_descriptions(cls, value: str) -> str:
        """Strip extra whitespace and markdown formatting from descriptions."""

        return _clean_description_text(value)

    @staticmethod
    def _clean_text(value: str) -> str:
        cleaned = value.strip().lower()
        if "(" in cleaned:
            cleaned = cleaned.split("(", 1)[0].strip()
        cleaned = cleaned.replace("-", " ").replace("_", " ")
        cleaned = " ".join(cleaned.split())
        return cleaned

    @field_validator("taxon_rank", mode="before")
    @classmethod
    def _normalise_taxon_rank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        key = cls._clean_text(text)
        return cls._TAXON_RANK_MAP.get(key, text)

    @field_validator("wikipedia_en", "wikipedia_de", mode="before")
    @classmethod
    def _normalise_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalise_url(value)

    @field_validator("iucn_conservation_status", mode="before")
    @classmethod
    def _normalise_iucn_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        key = cls._clean_text(text)
        canonical = cls._IUCN_STATUS_MAP.get(key)
        if canonical:
            return canonical
        parts = key.split()
        if len(parts) > 1 and len(parts[-1]) <= 3:
            trimmed = " ".join(parts[:-1])
            if trimmed:
                canonical = cls._IUCN_STATUS_MAP.get(trimmed)
                if canonical:
                    return canonical
        return text


class GeminiClientBase:
    """Shared helper for Gemini workflows."""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _research(self, prompt: str) -> str:
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

    def _structure(
        self,
        partially_structured_text: str,
        schema: Type[BaseModel],
        instructions: str | None = None,
        extra_instructions: str | None = None,
    ) -> BaseModel:
        base_instructions = (instructions or DEFAULT_STRUCTURE_INSTRUCTIONS).strip()
        prompt_parts = [base_instructions]
        if extra_instructions:
            prompt_parts.append(extra_instructions.strip())
        prompt = "\n\n".join(part for part in prompt_parts if part) + "\n\n" + partially_structured_text
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
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return schema.model_validate_json(response.text)

    async def _research_async(self, prompt: str) -> str:
        return await asyncio.to_thread(self._research, prompt)

    async def _structure_async(
        self,
        partially_structured_text: str,
        schema: Type[BaseModel],
        instructions: str | None = None,
        extra_instructions: str | None = None,
    ) -> BaseModel:
        return await asyncio.to_thread(
            self._structure,
            partially_structured_text,
            schema,
            instructions=instructions,
            extra_instructions=extra_instructions,
        )


class GeminiZooClient(GeminiClientBase):
    """Wrapper around the google-genai client for the two required calls."""

    def research_zoo(self, prompt: str) -> str:
        """Run the research-oriented Gemini call and return the raw text output."""
        return self._research(prompt)

    def structure_response(self, partially_structured_text: str) -> ZooRecord:
        """Convert the research output into a structured JSON payload."""
        extra_instructions = (
            "Extract the following text into the requested fields. "
            "The visitors field is supposed to contain the yearly number of visitors. "
            "Remove formatiing from the description fields, other than usual punctuation."
            "If a field is not present, leave it null instead of guessing."
        )
        return self._structure(
            partially_structured_text,
            ZooRecord,
            extra_instructions=extra_instructions,
        )

    async def research_zoo_async(self, prompt: str) -> str:
        """Async wrapper around :meth:`research_zoo`."""

        return await self._research_async(prompt)

    async def structure_response_async(self, partially_structured_text: str) -> ZooRecord:
        """Async wrapper around :meth:`structure_response`."""

        extra_instructions = (
            "Extract the following text into the requested fields. "
            "The visitors field is supposed to contain the yearly number of visitors. "
            "Remove formatiing from the description fields, other than usual punctuation."
            "If a field is not present, leave it null instead of guessing."
        )
        result = await self._structure_async(
            partially_structured_text,
            ZooRecord,
            extra_instructions=extra_instructions,
        )
        return cast(ZooRecord, result)


class GeminiCoordinateClient(GeminiClientBase):
    """Gemini helper specialised for zoo coordinate discovery."""

    def research_coordinates(self, prompt: str) -> str:
        return self._research(prompt)

    def structure_response(self, partially_structured_text: str) -> ZooCoordinateRecord:
        extra_instructions = (
            "Extract the decimal latitude and longitude in WGS84 format. "
            "Return them as JSON numbers (use null if you cannot confirm a value)."
        )
        return cast(
            ZooCoordinateRecord,
            self._structure(
                partially_structured_text,
                ZooCoordinateRecord,
                extra_instructions=extra_instructions,
            ),
        )

    async def research_coordinates_async(self, prompt: str) -> str:
        return await self._research_async(prompt)

    async def structure_response_async(
        self, partially_structured_text: str
    ) -> ZooCoordinateRecord:
        extra_instructions = (
            "Extract the decimal latitude and longitude in WGS84 format. "
            "Return them as JSON numbers (use null if you cannot confirm a value)."
        )
        result = await self._structure_async(
            partially_structured_text,
            ZooCoordinateRecord,
            extra_instructions=extra_instructions,
        )
        return cast(ZooCoordinateRecord, result)


class GeminiAnimalClient(GeminiClientBase):
    """Gemini helper specialised for animal enrichment."""

    def research_animal(self, prompt: str) -> str:
        return self._research(prompt)

    def structure_response(self, partially_structured_text: str) -> AnimalRecord:
        extra_instructions = (
            "Extract the following text into JSON fields named description_en, description_de, "
            "wikipedia_en, wikipedia_de, taxon_rank, and iucn_conservation_status. "
            "Keep the descriptions as plain text without markdown or bullet lists. "
            "For wikipedia URLs, provide the direct link or leave them null if they are missing. "
            "For taxon_rank, only allow 'species' or 'subspecies'. "
            "For iucn_conservation_status use one of the allowed values or null when unknown."
        )
        return self._structure(
            partially_structured_text,
            AnimalRecord,
            extra_instructions=extra_instructions,
        )

    async def research_animal_async(self, prompt: str) -> str:
        return await self._research_async(prompt)

    async def structure_response_async(self, partially_structured_text: str) -> AnimalRecord:
        extra_instructions = (
            "Extract the following text into JSON fields named description_en, description_de, "
            "wikipedia_en, wikipedia_de, taxon_rank, and iucn_conservation_status. "
            "Keep the descriptions as plain text without markdown or bullet lists. "
            "For wikipedia URLs, provide the direct link or leave them null if they are missing. "
            "For taxon_rank, only allow 'species' or 'subspecies'. "
            "For iucn_conservation_status use one of the allowed values or null when unknown."
        )
        result = await self._structure_async(
            partially_structured_text,
            AnimalRecord,
            extra_instructions=extra_instructions,
        )
        return cast(AnimalRecord, result)

