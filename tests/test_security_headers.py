"""Tests ensuring that the API includes secure HTTP headers on responses."""

from fastapi.testclient import TestClient

from app.config import SECURITY_HEADERS
from app.main import app


def test_security_headers_are_set():
    """The middleware should add the expected security headers to responses."""

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    for header, value in SECURITY_HEADERS.items():
        if header.lower() == "strict-transport-security":
            assert header not in response.headers
        else:
            assert response.headers.get(header) == value


def test_hsts_header_is_only_sent_for_https():
    """HSTS should be emitted only when the effective scheme is HTTPS."""

    client = TestClient(app)
    response = client.get("/", headers={"X-Forwarded-Proto": "https"})

    assert response.status_code == 200
    assert (
        response.headers.get("Strict-Transport-Security")
        == SECURITY_HEADERS["Strict-Transport-Security"]
    )
