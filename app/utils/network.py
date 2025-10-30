"""Network-related utility functions."""

from __future__ import annotations

import ipaddress

from typing import Final

from fastapi import Request

_CF_LATITUDE_HEADER = "cf-iplatitude"
_CF_LONGITUDE_HEADER = "cf-iplongitude"

_TRUSTED_PROXY_RANGES: Final[
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
] = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)


def _normalise_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _is_trusted_proxy(host: str | None) -> bool:
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in network for network in _TRUSTED_PROXY_RANGES)


def get_client_ip(request: Request) -> str:
    """Return the originating client IP address for a request."""

    host_ip: str | None = None
    trusted_proxy = False
    if request.client and request.client.host:
        host_ip = _normalise_ip(request.client.host)
        if host_ip is None:
            trusted_proxy = True
        elif not _is_trusted_proxy(request.client.host):
            return host_ip
        else:
            trusted_proxy = True

    if trusted_proxy:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            first = _normalise_ip(xff.split(",")[0])
            if first:
                return first

    if host_ip:
        return host_ip

    return "unknown"


def _header_to_float(
    request: Request,
    header: str,
    *,
    min_value: float,
    max_value: float,
) -> float | None:
    """Return the float value for a header if it falls within a valid range."""

    raw_value = request.headers.get(header)
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    if not (min_value <= value <= max_value):
        return None
    return value


def get_cloudflare_location(request: Request) -> tuple[float | None, float | None]:
    """Extract latitude/longitude estimates from Cloudflare geolocation headers."""

    latitude = _header_to_float(
        request,
        _CF_LATITUDE_HEADER,
        min_value=-90.0,
        max_value=90.0,
    )
    longitude = _header_to_float(
        request,
        _CF_LONGITUDE_HEADER,
        min_value=-180.0,
        max_value=180.0,
    )
    if latitude is None or longitude is None:
        return None, None
    return latitude, longitude
