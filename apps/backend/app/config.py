"""Environment-driven configuration for the FastAPI application."""

from __future__ import annotations

import os
import re
from typing import Final
from urllib.parse import urlsplit


def _get_env(name: str, *, default: str | None = None, required: bool = False) -> str | None:
    value = os.getenv(name)
    if value is None:
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return default
    return value.strip()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    value = _get_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


JWT_ALGORITHM: Final[str] = "HS256"

_hs_secret = _get_env("JWT_SECRET") or _get_env("SECRET_KEY")
if not _hs_secret:
    raise RuntimeError("JWT_SECRET (or legacy SECRET_KEY) is required for HS256 JWTs")

JWT_SIGNING_KEY: Final[str] = _hs_secret
JWT_VERIFYING_KEY: Final[str] = _hs_secret

JWT_KID = _get_env("JWT_KID")

ACCESS_TOKEN_TTL = _get_int("ACCESS_TOKEN_TTL", 900)
ACCESS_TOKEN_LEEWAY = _get_int("ACCESS_TOKEN_LEEWAY", 60)

def _normalize_str_env(name: str, default: str) -> str:
    """Get string environment variable and normalize it (strip whitespace, uppercase)."""
    value = _get_env(name, default=default)
    if value is None:
        return default
    return value.strip().upper()

# Preserve legacy configuration import paths used in the existing codebase/tests.
ACCESS_TOKEN_EXPIRE_MINUTES = max(1, ACCESS_TOKEN_TTL // 60)

REFRESH_IDLE_TTL = _get_int("REFRESH_IDLE_TTL", 1800)
REFRESH_ABS_TTL = _get_int("REFRESH_ABS_TTL", 1_209_600)

REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = _get_env("CSRF_COOKIE_NAME", default="refresh_csrf") or "refresh_csrf"
CSRF_HEADER_NAME = _get_env("CSRF_HEADER_NAME", default="X-CSRF") or "X-CSRF"

COOKIE_SAMESITE = (_get_env("COOKIE_SAMESITE", default="Lax") or "Lax").capitalize()
if COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
    raise RuntimeError("COOKIE_SAMESITE must be one of: Lax, Strict, None")

COOKIE_DOMAIN = _get_env("COOKIE_DOMAIN")
COOKIE_SECURE = _get_bool("COOKIE_SECURE", default=True)

_token_pepper = _get_env("TOKEN_PEPPER", required=True)
if _token_pepper is None:
    raise RuntimeError("TOKEN_PEPPER is required")
TOKEN_PEPPER: Final[str] = _token_pepper

EMAIL_VERIFICATION_TTL_MINUTES = _get_int("EMAIL_VERIFICATION_TTL_MINUTES", 30)
EMAIL_VERIFICATION_RESEND_COOLDOWN = _get_int(
    "EMAIL_VERIFICATION_RESEND_COOLDOWN", 60
)
EMAIL_VERIFICATION_DAILY_LIMIT = _get_int("EMAIL_VERIFICATION_DAILY_LIMIT", 5)
PASSWORD_RESET_TTL_MINUTES = _get_int("PASSWORD_RESET_TTL_MINUTES", 30)
PASSWORD_RESET_REQUEST_COOLDOWN = _get_int(
    "PASSWORD_RESET_REQUEST_COOLDOWN", 300
)
PASSWORD_RESET_DAILY_LIMIT = _get_int("PASSWORD_RESET_DAILY_LIMIT", 3)
APP_BASE_URL = (
    _get_env("APP_BASE_URL", default="http://localhost:5173")
    or "http://localhost:5173"
)

_site_base_url = _get_env("SITE_BASE_URL")
SITE_BASE_URL = _site_base_url or APP_BASE_URL


def _is_absolute_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except Exception:  # pragma: no cover - defensive guard for malformed URLs
        return False
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


if not _is_absolute_http_url(SITE_BASE_URL):
    raise RuntimeError(
        f"SITE_BASE_URL must be an absolute http(s) URL, got: {SITE_BASE_URL!r}"
    )

_site_languages_env = _get_env("SITE_LANGUAGES")
if _site_languages_env is None:
    _site_languages_raw = "en,de"
else:
    _site_languages_raw = _site_languages_env
    if not _site_languages_raw:
        raise RuntimeError("SITE_LANGUAGES must list at least one language code")

_site_languages = [
    item.strip() for item in _site_languages_raw.split(",") if item.strip()
]
if not _site_languages:
    raise RuntimeError("SITE_LANGUAGES must list at least one language code")

_lang_pattern = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
for code in _site_languages:
    if not _lang_pattern.fullmatch(code):
        raise RuntimeError(
            "SITE_LANGUAGES entries must be valid BCP 47 language tags; "
            f"got: {code!r}"
        )

SITE_LANGUAGES: Final[tuple[str, ...]] = tuple(_site_languages)
SITE_DEFAULT_LANGUAGE: Final[str] = SITE_LANGUAGES[0]

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (_get_env("ALLOWED_ORIGINS", default="") or "").split(",")
    if origin.strip()
]

def _read_header(name: str, default: str | None) -> str | None:
    """Fetch an environment override for a security header."""

    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or None


# Security header defaults keep browsers on HTTPS and enforce safe resource loading.
DEFAULT_STRICT_TRANSPORT_SECURITY = "max-age=63072000; includeSubDomains; preload"
DEFAULT_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)
DEFAULT_X_FRAME_OPTIONS = "DENY"
DEFAULT_X_CONTENT_TYPE_OPTIONS = "nosniff"
DEFAULT_REFERRER_POLICY = "no-referrer"

STRICT_TRANSPORT_SECURITY = _read_header(
    "STRICT_TRANSPORT_SECURITY", DEFAULT_STRICT_TRANSPORT_SECURITY
)
CONTENT_SECURITY_POLICY = _read_header(
    "CONTENT_SECURITY_POLICY", DEFAULT_CONTENT_SECURITY_POLICY
)

SECURITY_HEADERS = {
    "X-Frame-Options": DEFAULT_X_FRAME_OPTIONS,
    "X-Content-Type-Options": DEFAULT_X_CONTENT_TYPE_OPTIONS,
}

if STRICT_TRANSPORT_SECURITY:
    SECURITY_HEADERS["Strict-Transport-Security"] = STRICT_TRANSPORT_SECURITY

if CONTENT_SECURITY_POLICY:
    SECURITY_HEADERS["Content-Security-Policy"] = CONTENT_SECURITY_POLICY

REFERRER_POLICY = _read_header("REFERRER_POLICY", DEFAULT_REFERRER_POLICY)

if REFERRER_POLICY:
    SECURITY_HEADERS["Referrer-Policy"] = REFERRER_POLICY

# Image serving mode: WIKIMEDIA (dev, hotlink from Commons) or S3 (prod, self-hosted)
IMAGE_URL_MODE = _normalize_str_env("IMAGE_URL_MODE", default="WIKIMEDIA")
if IMAGE_URL_MODE not in {"WIKIMEDIA", "S3"}:
    raise RuntimeError("IMAGE_URL_MODE must be either WIKIMEDIA or S3")
