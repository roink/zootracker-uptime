from typing import Annotated

from fastapi import HTTPException, Query, Request, status

from ._validation import get_request_coords


def resolve_coords(
    request: Request,
    latitude: Annotated[float | None, Query()] = None,
    longitude: Annotated[float | None, Query()] = None,
) -> tuple[float | None, float | None]:
    """FastAPI dependency to resolve coordinates from query params or headers."""
    return get_request_coords(request, latitude, longitude)


def require_json(request: Request) -> None:
    """Ensure that a request was submitted with a JSON content type."""

    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
