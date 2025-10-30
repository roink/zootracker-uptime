"""Utilities for working with IUCN conservation status codes."""
from __future__ import annotations

# Canonical IUCN status codes and human readable labels
IUCN_CODES: dict[str, str] = {
    "EX": "Extinct",
    "EW": "Extinct in the Wild",
    "CR": "Critically Endangered",
    "EN": "Endangered",
    "VU": "Vulnerable",
    "NT": "Near Threatened",
    "LC": "Least Concern",
    "DD": "Data Deficient",
    "NE": "Not Evaluated",
}

# Lowercase synonyms mapping to canonical codes
_IUCN_SYNONYMS: dict[str, str] = {
    "extinct": "EX",
    "extinct in the wild": "EW",
    "critically endangered": "CR",
    "endangered": "EN",
    "vulnerable": "VU",
    "near threatened": "NT",
    "least concern": "LC",
    "data deficient": "DD",
    "not evaluated": "NE",
}


def normalize_status(value: str | None) -> str | None:
    """Return a canonical IUCN status code for *value*.

    The lookup is case-insensitive and accepts both the short code and full
    description. Unknown values return ``None`` so callers can skip storing
    invalid statuses.
    """

    if not value:
        return None
    cleaned = value.strip()
    upper = cleaned.upper()
    if upper in IUCN_CODES:
        return upper
    return _IUCN_SYNONYMS.get(cleaned.lower())
