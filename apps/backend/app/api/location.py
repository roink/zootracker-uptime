"""Endpoints related to location estimation for clients."""

from fastapi import APIRouter, Request, Response

from .. import schemas
from ..metrics import increment_location_estimate_requests
from ..utils.network import get_cloudflare_location

router = APIRouter()

# Requires Cloudflare's "Add visitor location headers" Managed Transform
# (or a similar rule) to be enabled so the CDN injects latitude/longitude headers.
@router.get(
    "/location/estimate",
    response_model=schemas.LocationEstimate,
    summary="Estimate the client's location from Cloudflare headers",
    description=(
        "Return coarse latitude and longitude derived from Cloudflare's visitor "
        "location headers. Both values are ``null`` when Cloudflare does not "
        "provide a coordinate estimate."
    ),
    responses={
        200: {
            "description": (
                "Estimated coordinates derived from Cloudflare headers. Values are "
                "``null`` when no estimate is available."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "with_coordinates": {
                            "summary": "Cloudflare provided coordinates",
                            "value": {"latitude": 47.4, "longitude": 8.5},
                        },
                        "unknown": {
                            "summary": "No coordinate estimate available",
                            "value": {"latitude": None, "longitude": None},
                        },
                    }
                }
            },
        }
    },
)
def estimate_location(request: Request, response: Response) -> schemas.LocationEstimate:
    """Return a best-effort location estimate based on Cloudflare headers."""

    response.headers["Cache-Control"] = "private, no-store"

    latitude, longitude = get_cloudflare_location(request)
    source = "cloudflare" if latitude is not None and longitude is not None else "unknown"
    increment_location_estimate_requests(source)
    return schemas.LocationEstimate(latitude=latitude, longitude=longitude)
