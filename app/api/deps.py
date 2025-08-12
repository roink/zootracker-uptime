from fastapi import Query, Request

from ._validation import get_request_coords


def resolve_coords(
    request: Request,
    latitude: float | None = Query(default=None),
    longitude: float | None = Query(default=None),
) -> tuple[float | None, float | None]:
    """FastAPI dependency to resolve coordinates from query params or headers."""
    return get_request_coords(request, latitude, longitude)
