"""HTTP response helpers for consistent caching behaviour."""

from fastapi import Response


def set_personalized_cache_headers(response: Response) -> None:
    """Prevent caching of responses that include user-personalized data."""

    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    existing_vary = response.headers.get("Vary")
    if existing_vary:
        tokens = [token.strip() for token in existing_vary.split(",") if token.strip()]
        if not any(token.lower() == "authorization" for token in tokens):
            tokens.append("Authorization")
        response.headers["Vary"] = ", ".join(tokens)
    else:
        response.headers["Vary"] = "Authorization"
