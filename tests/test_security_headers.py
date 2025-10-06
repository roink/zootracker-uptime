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
        assert response.headers.get(header) == value
