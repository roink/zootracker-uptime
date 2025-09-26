"""CLI helper to run the Gemini zoo enrichment workflow for a single zoo."""

from __future__ import annotations

import argparse
import json

from gemini_utils import (
    GeminiZooClient,
    fetch_zoo_metadata,
    get_gemini_api_key,
    get_database_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Gemini research output and structured JSON for a zoo.",
    )
    parser.add_argument("zoo_id", type=int, help="Identifier from the zoo table")
    args = parser.parse_args()

    api_key = get_gemini_api_key()
    db_path = get_database_path()
    metadata = fetch_zoo_metadata(args.zoo_id, db_path=db_path)

    print(
        f"Loaded zoo {metadata.zoo_id}: {metadata.name} "
        f"({metadata.city}, {metadata.country_en or 'Unknown country'})"
    )
    print("Country ID:", metadata.country_id)

    client = GeminiZooClient(api_key)

    prompt = metadata.to_prompt()
    print("\n=== Research Prompt ===\n")
    print(prompt)

    research_text = client.research_zoo(prompt)
    print("\n=== Gemini Research Output ===\n")
    print(research_text)

    if research_text:
        structured = client.structure_response(research_text)
    else:
        structured = {}

    print("\n=== Structured JSON ===\n")
    print(json.dumps(structured, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

