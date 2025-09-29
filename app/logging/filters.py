"""Logging filters that enrich and sanitise records."""

from __future__ import annotations

import logging

from .context import (
    client_ip_anonymized_ctx_var,
    client_ip_ctx_var,
    client_ip_raw_ctx_var,
    request_id_ctx_var,
    user_id_ctx_var,
)
from .ip_utils import anonymize_ip
from .privacy import sanitize_value


class PrivacyFilter(logging.Filter):
    """Ensure sensitive headers or payloads never hit the logs."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        for key in list(record.__dict__.keys()):
            if key in {"exc_info", "exc_text", "stack_info", "msg"}:
                continue
            record.__dict__[key] = sanitize_value(key, record.__dict__[key])
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(sanitize_value("arg", arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: sanitize_value(k, v) for k, v in record.args.items()}
        return True


class RequestContextFilter(logging.Filter):
    """Attach request scoped context variables to log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        request_id = request_id_ctx_var.get(None)
        if request_id:
            record.request_id = request_id
        user_id = user_id_ctx_var.get(None)
        if user_id:
            record.user_id = user_id
        client_ip = client_ip_ctx_var.get(None)
        if client_ip:
            record.client_ip = client_ip
        return True


class IPOverrideFilter(logging.Filter):
    """Override ``client_ip`` for a specific handler."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        valid_modes = {"raw", "anonymized"}
        if mode not in valid_modes:
            raise ValueError(f"Unsupported IP override mode: {mode}")
        self.mode = mode

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        original = getattr(record, "client_ip", None)
        raw_ip = getattr(record, "client_ip_raw", None) or client_ip_raw_ctx_var.get(None)
        if self.mode == "raw":
            if raw_ip:
                record.client_ip = raw_ip
            else:
                record.client_ip = original
            return True

        anonymized = (
            getattr(record, "client_ip_anonymized", None)
            or client_ip_anonymized_ctx_var.get(None)
        )
        if anonymized is None and raw_ip:
            anonymized = anonymize_ip(raw_ip, mode="anonymized")
        if anonymized is not None:
            record.client_ip = anonymized
        else:
            record.client_ip = original
        for attr in ("client_ip_raw", "client_ip_anonymized"):
            if hasattr(record, attr):
                delattr(record, attr)
        return True
