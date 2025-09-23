"""Tests for the location estimation endpoint."""

import pytest

from .conftest import client


@pytest.mark.parametrize(
    "headers,expected",
    [
        pytest.param(
            {"CF-IPLatitude": "47.1234", "CF-IPLongitude": "8.5432"},
            {"latitude": 47.1234, "longitude": 8.5432},
            id="valid",
        ),
        pytest.param({}, {"latitude": None, "longitude": None}, id="no-headers"),
        pytest.param(
            {"CF-IPLatitude": "47.1234"},
            {"latitude": None, "longitude": None},
            id="lat-only",
        ),
        pytest.param(
            {"CF-IPLongitude": "8.5432"},
            {"latitude": None, "longitude": None},
            id="lon-only",
        ),
        pytest.param(
            {"CF-IPLatitude": "not-a-number", "CF-IPLongitude": "8.5432"},
            {"latitude": None, "longitude": None},
            id="non-numeric",
        ),
        pytest.param(
            {"CF-IPLatitude": "47.1234", "CF-IPLongitude": "200.0"},
            {"latitude": None, "longitude": None},
            id="lon-out-of-range",
        ),
        pytest.param(
            {"CF-IPLatitude": "91", "CF-IPLongitude": "8.0"},
            {"latitude": None, "longitude": None},
            id="lat-out-of-range",
        ),
        pytest.param(
            {"CF-IPLatitude": "47.1234", "cf-iplongitude": "8.5432"},
            {"latitude": 47.1234, "longitude": 8.5432},
            id="mixed-case",
        ),
    ],
)
def test_location_estimate_handles_cloudflare_headers(headers, expected):
    response = client.get("/location/estimate", headers=headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.json() == expected
