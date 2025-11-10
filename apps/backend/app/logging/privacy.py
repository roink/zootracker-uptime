"""Utilities for removing sensitive data from log records."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode

SENSITIVE_KEYWORDS = {
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
    "x-csrf-token",
}
TOKEN_KEYWORDS = {"token", "authorization", "apikey", "api_key", "x-api-key"}
MASKED_VALUE = "<redacted>"
MAX_FIELD_LENGTH = 1024

GEO_LAT_KEY_PATTERN = re.compile(r"(?:^|_)(lat|latitude)(?:$|_)")
GEO_LON_KEY_PATTERN = re.compile(r"(?:^|_)(lon|longitude)(?:$|_)")
GEO_PAIR_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")

QUERY_STRING_KEYS = {"url_query", "query_string"}


def _mask_token(value: str) -> str:
    value = value.strip()
    if not value:
        return MASKED_VALUE
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _normalize_key(key: str) -> str:
    """Return a snake_case lower representation of ``key`` for comparisons."""

    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", snake)
    return snake.strip("_").lower()


def _round_coordinate(value: float) -> float:
    rounded = round(value, 1)
    if rounded == 0:
        return 0.0
    return rounded


def _coarsen_coordinate(value: Any, minimum: float, maximum: float) -> Any:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if minimum <= numeric <= maximum:
            return _round_coordinate(numeric)
        return value
    if isinstance(value, str):
        try:
            numeric = float(value.strip())
        except (TypeError, ValueError):
            return value
        if minimum <= numeric <= maximum:
            return f"{_round_coordinate(numeric):.1f}"
    return value


def _coarsen_lat_lon_string(value: str) -> str:
    match = GEO_PAIR_PATTERN.match(value)
    if not match:
        return value
    try:
        lat = float(match.group(1))
        lon = float(match.group(2))
    except (TypeError, ValueError):
        return value
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return value
    return f"{_round_coordinate(lat):.1f},{_round_coordinate(lon):.1f}"


def _stringify_query_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _coarsen_query_parameter(key: str, value: str) -> str:
    normalized = _normalize_key(key)

    if GEO_LAT_KEY_PATTERN.search(normalized):
        return _stringify_query_value(_coarsen_coordinate(value, -90.0, 90.0))
    if GEO_LON_KEY_PATTERN.search(normalized):
        return _stringify_query_value(_coarsen_coordinate(value, -180.0, 180.0))

    if normalized.startswith("geo") or "geolocation" in normalized:
        return _coarsen_lat_lon_string(value)

    return _coarsen_lat_lon_string(value)


def _sanitize_query_string(query: str) -> str:
    try:
        pairs = parse_qsl(query, keep_blank_values=True)
    except ValueError:
        return query

    changed = False
    sanitized: list[tuple[str, str]] = []

    for key, value in pairs:
        new_value = _coarsen_query_parameter(key, value)
        if new_value != value:
            changed = True
        sanitized.append((key, new_value))

    if not changed:
        return query

    return urlencode(sanitized, doseq=True)


def _apply_geolocation_policy(key: str | None, value: Any) -> Any:
    def _maybe_sanitize_query_string(raw: str) -> str:
        if "=" in raw and ("&" in raw or raw.count("=") > 1):
            return _sanitize_query_string(raw)
        return _coarsen_lat_lon_string(raw)

    if key is None:
        if isinstance(value, str):
            return _maybe_sanitize_query_string(value)
        return value

    normalized = _normalize_key(key)

    if normalized in QUERY_STRING_KEYS:
        if isinstance(value, str):
            return _sanitize_query_string(value)
        return value

    if GEO_LAT_KEY_PATTERN.search(normalized):
        return _coarsen_coordinate(value, -90.0, 90.0)
    if GEO_LON_KEY_PATTERN.search(normalized):
        return _coarsen_coordinate(value, -180.0, 180.0)

    if (normalized.startswith("geo") or "geolocation" in normalized) and isinstance(
        value, str
    ):
        return _coarsen_lat_lon_string(value)

    if isinstance(value, str):
        return _maybe_sanitize_query_string(value)
    return value


def sanitize_value(key: Any, value: Any) -> Any:
    """Redact sensitive information and limit field size."""

    if isinstance(key, bytes):
        key_text = key.decode("utf-8", "ignore")
    elif isinstance(key, str):
        key_text = key
    else:
        key_text = None
    lowered = key_text.lower() if key_text is not None else ""
    value = _apply_geolocation_policy(key_text, value)
    if isinstance(value, str):
        if any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
            if any(keyword in lowered for keyword in TOKEN_KEYWORDS):
                return _mask_token(value)
            return MASKED_VALUE
        if len(value) > MAX_FIELD_LENGTH:
            return value[:MAX_FIELD_LENGTH] + "…[truncated]"
        return value
    if isinstance(value, dict):
        return {k: sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        container = type(value)
        sanitized = [sanitize_value(key, item) for item in value]
        if container is tuple:
            return tuple(sanitized)
        if container is set:
            return set(sanitized)
        return sanitized
    return value
