import os


def _normalize_secret(value: str) -> str:
    """Strip surrounding whitespace so simple copy/paste mistakes are ignored."""

    return value.strip()


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is required. Generate a strong value (e.g., openssl rand -hex 32)."
    )

SECRET_KEY = _normalize_secret(SECRET_KEY)

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY must be at least 32 characters (32 bytes) for HS256. Use a long, random value."
    )

_WEAK_SECRET_KEYS = {
    "secret",
    "changeme",
    "password",
    "test-secret-key",
    "test-secret-key-change-me",
}
if SECRET_KEY.lower() in _WEAK_SECRET_KEYS:
    raise RuntimeError(
        "SECRET_KEY is too weak; use a long, random value such as openssl rand -hex 32."
    )
ALGORITHM = "HS256"
# Allow token lifetime to be configured via environment variable
# Defaults to 30 minutes when not provided
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Comma separated list of origins allowed to access the API via CORS
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
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
