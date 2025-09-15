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
