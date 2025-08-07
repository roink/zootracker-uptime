from starlette.requests import Request

from app.utils.network import get_client_ip


def make_request(headers=None, client_host="1.2.3.4"):
    scope = {
        "type": "http",
        "headers": [],
        "client": (client_host, 1234),
    }
    if headers:
        scope["headers"] = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(scope)


def test_get_client_ip_prefers_x_forwarded_for():
    req = make_request(headers={"X-Forwarded-For": "203.0.113.5, 70.41.3.18"}, client_host="5.5.5.5")
    assert get_client_ip(req) == "203.0.113.5"


def test_get_client_ip_fallback_to_client_host():
    req = make_request()
    assert get_client_ip(req) == "1.2.3.4"
