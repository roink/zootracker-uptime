from starlette.requests import Request

from app.logging import anonymize_ip
from app.utils.network import get_client_ip

def make_request(headers=None, client_host="1.2.3.4"):
    scope = {
        "type": "http",
        "headers": [],
        "client": (client_host, 1234) if client_host else None,
    }
    if headers:
        scope["headers"] = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(scope)


async def test_get_client_ip_prefers_direct_client_host(client):
    req = make_request(client_host="5.5.5.5")
    assert get_client_ip(req) == "5.5.5.5"


async def test_get_client_ip_uses_x_forwarded_for_for_trusted_proxy(client):
    req = make_request(
        headers={"X-Forwarded-For": "203.0.113.5, 70.41.3.18"},
        client_host="10.1.1.1",
    )
    assert get_client_ip(req) == "203.0.113.5"


async def test_get_client_ip_does_not_trust_cf_connecting_ip(client):
    req = make_request(headers={"CF-Connecting-IP": "203.0.113.5"}, client_host=None)
    assert get_client_ip(req) == "unknown"


async def test_get_client_ip_handles_invalid_values(client):
    req = make_request(headers={"X-Forwarded-For": "not-an-ip"}, client_host=None)
    assert get_client_ip(req) == "unknown"


async def test_anonymize_ip_returns_network_with_prefix_for_ipv4(client, monkeypatch):
    monkeypatch.setenv("LOG_IP_MODE", "anonymized")
    assert anonymize_ip("203.0.113.5") == "203.0.113.0/24"


async def test_anonymize_ip_returns_network_with_prefix_for_ipv6(client, monkeypatch):
    monkeypatch.setenv("LOG_IP_MODE", "anonymized")
    assert anonymize_ip("2001:db8::1234") == "2001:db8::/64"
