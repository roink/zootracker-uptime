"""Environment-driven configuration for the FastAPI application."""

from __future__ import annotations

import os
from typing import Final


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


JWT_ALGORITHM: Final[str] = "HS256"

_hs_secret = _get_env("JWT_SECRET") or _get_env("SECRET_KEY")
if not _hs_secret:
    raise RuntimeError("JWT_SECRET (or legacy SECRET_KEY) is required for HS256 JWTs")

JWT_SIGNING_KEY: Final[str] = _hs_secret
JWT_VERIFYING_KEY: Final[str] = _hs_secret

JWT_KID = _get_env("JWT_KID")

ACCESS_TOKEN_TTL = int(_get_env("ACCESS_TOKEN_TTL", default="900"))
ACCESS_TOKEN_LEEWAY = int(_get_env("ACCESS_TOKEN_LEEWAY", default="60"))

# Preserve legacy configuration import paths used in the existing codebase/tests.
ACCESS_TOKEN_EXPIRE_MINUTES = max(1, ACCESS_TOKEN_TTL // 60)

REFRESH_IDLE_TTL = int(_get_env("REFRESH_IDLE_TTL", default="1800"))
REFRESH_ABS_TTL = int(_get_env("REFRESH_ABS_TTL", default="1209600"))

REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = _get_env("CSRF_COOKIE_NAME", default="refresh_csrf") or "refresh_csrf"
CSRF_HEADER_NAME = _get_env("CSRF_HEADER_NAME", default="X-CSRF") or "X-CSRF"

COOKIE_SAMESITE = (_get_env("COOKIE_SAMESITE", default="Lax") or "Lax").capitalize()
if COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
    raise RuntimeError("COOKIE_SAMESITE must be one of: Lax, Strict, None")

COOKIE_DOMAIN = _get_env("COOKIE_DOMAIN")
COOKIE_SECURE = _get_bool("COOKIE_SECURE", default=True)

TOKEN_PEPPER = _get_env("TOKEN_PEPPER", required=True)

EMAIL_VERIFICATION_TTL_MINUTES = int(
    _get_env("EMAIL_VERIFICATION_TTL_MINUTES", default="30")
)
EMAIL_VERIFICATION_RESEND_COOLDOWN = int(
    _get_env("EMAIL_VERIFICATION_RESEND_COOLDOWN", default="60")
)
EMAIL_VERIFICATION_DAILY_LIMIT = int(
    _get_env("EMAIL_VERIFICATION_DAILY_LIMIT", default="5")
)
APP_BASE_URL = _get_env("APP_BASE_URL", default="http://localhost:5173") or "http://localhost:5173"

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
