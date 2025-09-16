from .conftest import client


def test_cors_allows_configured_origin():
    """Preflight requests from allowed origins should succeed."""
    resp = client.options(
        "/animals",
        headers={
            "Origin": "http://allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert (
        resp.headers.get("access-control-allow-origin") == "http://allowed.example"
    )


def test_cors_rejects_other_origins():
    """Origins not on the whitelist fail the CORS check."""
    resp = client.options(
        "/animals",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers
