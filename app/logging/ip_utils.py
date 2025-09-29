"""Utilities for handling IP address logging policies."""

from __future__ import annotations

import ipaddress
import os
from typing import Optional


def anonymize_ip(ip: Optional[str], mode: Optional[str] = None) -> Optional[str]:
    """Return an IP address formatted according to the configured mode."""

    mode_value = (mode or os.getenv("LOG_IP_MODE", "full")).lower()
    if mode_value not in {"full", "anonymized", "off"}:
        mode_value = "full"

    if mode_value == "off":
        return None

    if not ip or ip == "unknown":
        return "unknown"

    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return "unknown"

    if mode_value == "anonymized":
        prefix = 24 if parsed.version == 4 else 64
        network = ipaddress.ip_network(f"{parsed}/{prefix}", strict=False)
        return network.with_prefixlen

    return str(parsed)
