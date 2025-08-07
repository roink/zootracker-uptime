"""Network-related utility functions."""

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """Return the client IP address from a request.

    Prefers the first value in the ``X-Forwarded-For`` header but falls back
    to ``request.client.host``. Returns ``"unknown"`` when the information is
    unavailable.
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        ip = xff.split(",")[0].strip()
        if ip:
            return ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
