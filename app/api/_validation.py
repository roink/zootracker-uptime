import logging

from fastapi import HTTPException, Request, status


def validate_coords(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) ^ (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide both latitude and longitude together."
        )
    if latitude is None:
        return
    if not (-90 <= latitude <= 90):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid latitude")
    if not (-180 <= longitude <= 180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid longitude")


def get_request_coords(
    request: Request, latitude: float | None, longitude: float | None
) -> tuple[float | None, float | None]:
    """Return valid coordinates using query params or Cloudflare headers.

    If ``latitude`` and ``longitude`` are provided explicitly they are
    validated and returned. Otherwise this looks for Cloudflare geolocation
    headers (``cf-iplatitude``/``cf-iplongitude``) and returns them when
    valid. Invalid, partial or missing values result in ``(None, None)`` so
    the server continues to work even when location data is unavailable.
    """

    if latitude is not None or longitude is not None:
        validate_coords(latitude, longitude)
        return latitude, longitude

    lat_hdr = request.headers.get("cf-iplatitude")
    lon_hdr = request.headers.get("cf-iplongitude")
    if lat_hdr is None or lon_hdr is None:
        return None, None
    try:
        lat = float(lat_hdr)
        lon = float(lon_hdr)
    except (TypeError, ValueError):
        return None, None

    try:
        validate_coords(lat, lon)
    except HTTPException:
        return None, None

    logging.getLogger(__name__).debug(
        "Using Cloudflare geolocation headers lat=%.1f lon=%.1f",
        round(lat, 1),
        round(lon, 1),
    )
    return lat, lon
