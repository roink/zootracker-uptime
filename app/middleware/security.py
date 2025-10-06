"""Middleware that injects security headers for every response."""

from collections.abc import Mapping

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """Apply configured security headers to every response.

    Using a middleware keeps the logic centralised and ensures headers are present on
    both success and error responses.
    """

    def __init__(self, app: ASGIApp, headers: Mapping[str, str | None] | None = None) -> None:
        super().__init__(app)
        self._headers: Mapping[str, str | None] = headers or {}

    async def dispatch(self, request, call_next):  # type: ignore[override]
        response = await call_next(request)

        scheme = request.url.scheme
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        is_https = scheme == "https" or forwarded_proto == "https"

        for header, value in self._headers.items():
            if not value:
                continue
            if header.lower() == "strict-transport-security" and not is_https:
                continue
            response.headers[header] = value
        return response

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(headers={dict(self._headers)!r})"
