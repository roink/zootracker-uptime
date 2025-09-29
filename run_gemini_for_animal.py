"""CLI helper to run the Gemini animal enrichment workflow for a single animal."""

from __future__ import annotations

import argparse
import json

from gemini_utils import (
    GeminiAnimalClient,
    fetch_animal_metadata,
    get_database_path,
    get_gemini_api_key,
)
from pydantic import ValidationError


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Gemini research output and structured JSON for an animal.",
    )
    parser.add_argument(
        "art",
        type=str,
        help="Primary key from the animal table",
    )
    args = parser.parse_args()

    api_key = get_gemini_api_key()
    db_path = get_database_path()
    metadata = fetch_animal_metadata(args.art, db_path=db_path)

    print(f"Loaded animal {metadata.art}")
    print("Latin name:", metadata.latin_name or "Unknown")
    print("German name:", metadata.name_de or "Unknown")
    print("English name:", metadata.name_en or "Unknown")
    print("Class:", metadata.klasse_en or metadata.klasse_de or "Unknown")
    print("Order:", metadata.ordnung_en or metadata.ordnung_de or "Unknown")
    print("Family:", metadata.familie_en or metadata.familie_de or "Unknown")

    client = GeminiAnimalClient(api_key)

    prompt = metadata.to_prompt()
    print("\n=== Research Prompt ===\n")
    print(prompt)

    research_text = client.research_animal(prompt)
    print("\n=== Gemini Research Output ===\n")
    print(research_text)

    structured = {}
    if research_text:
        try:
            structured_record = client.structure_response(research_text)
        except ValidationError as exc:
            print("\nFailed to structure Gemini output:")
            print(exc)
        else:
            structured = structured_record.model_dump()

    print("\n=== Structured JSON ===\n")
    print(json.dumps(structured, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
