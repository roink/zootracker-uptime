"""Central logging configuration for the Zoo Tracker backend.

This module provides helpers to initialise structured JSON logging that is
compatible with Elastic Common Schema (ECS) style field names. It also exposes
context variables so request scoped values such as ``request_id`` and
``user_id`` can be injected into every log record.
"""

from __future__ import annotations

import ipaddress
import logging
import logging.config
import os
import re
import traceback
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import WatchedFileHandler
from typing import Any

from pythonjsonlogger import jsonlogger

# ---------------------------------------------------------------------------
# Request scoped context helpers
# ---------------------------------------------------------------------------

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx_var: ContextVar[str | None] = ContextVar("user_id", default=None)
client_ip_ctx_var: ContextVar[str | None] = ContextVar("client_ip", default=None)
client_ip_raw_ctx_var: ContextVar[str | None] = ContextVar("client_ip_raw", default=None)
client_ip_anonymized_ctx_var: ContextVar[str | None] = ContextVar(
    "client_ip_anonymized", default=None
)


@dataclass
class RequestContextTokens:
    """Container storing tokens for context variables set per request."""

    request_id_token: Token[str | None]
    user_id_token: Token[str | None]
    client_ip_token: Token[str | None]
    client_ip_raw_token: Token[str | None]
    client_ip_anonymized_token: Token[str | None]


def bind_request_context(
    request_id: str,
    client_ip: str | None = None,
    *,
    client_ip_raw: str | None = None,
    client_ip_anonymized: str | None = None,
) -> RequestContextTokens:
    """Bind request level context values.

    Returns a :class:`RequestContextTokens` object that must be passed to
    :func:`reset_request_context` when the request finishes.
    """

    if client_ip_raw is None:
        client_ip_raw = client_ip
    if client_ip_anonymized is None and client_ip_raw:
        client_ip_anonymized = anonymize_ip(client_ip_raw, mode="anonymized")

    return RequestContextTokens(
        request_id_ctx_var.set(request_id),
        user_id_ctx_var.set(None),
        client_ip_ctx_var.set(client_ip),
        client_ip_raw_ctx_var.set(client_ip_raw),
        client_ip_anonymized_ctx_var.set(client_ip_anonymized),
    )


def reset_request_context(tokens: RequestContextTokens) -> None:
    """Reset request scoped context variables using the provided tokens."""

    request_id_ctx_var.reset(tokens.request_id_token)
    user_id_ctx_var.reset(tokens.user_id_token)
    client_ip_ctx_var.reset(tokens.client_ip_token)
    client_ip_raw_ctx_var.reset(tokens.client_ip_raw_token)
    client_ip_anonymized_ctx_var.reset(tokens.client_ip_anonymized_token)


def set_user_context(user_id: str | None) -> None:
    """Store the current user id in the context for downstream log records."""

    user_id_ctx_var.set(user_id)


def get_request_id() -> str | None:
    """Return the current request id if one is bound."""

    return request_id_ctx_var.get(None)


def get_user_id() -> str | None:
    """Return the user id stored in the context, if available."""

    return user_id_ctx_var.get(None)


def get_client_ip() -> str | None:
    """Return the client IP stored in the context, if available."""

    return client_ip_ctx_var.get(None)


def get_client_ip_raw() -> str | None:
    """Return the raw client IP stored in the context, if available."""

    return client_ip_raw_ctx_var.get(None)


def get_client_ip_anonymized() -> str | None:
    """Return the anonymized client IP stored in the context, if available."""

    return client_ip_anonymized_ctx_var.get(None)


# ---------------------------------------------------------------------------
# Privacy helpers
# ---------------------------------------------------------------------------

SENSITIVE_KEYWORDS = {
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "set-cookie",
}
TOKEN_KEYWORDS = {"token", "authorization", "apikey", "api_key"}
MASKED_VALUE = "<redacted>"
MAX_FIELD_LENGTH = 1024

GEO_LAT_KEY_PATTERN = re.compile(r"(?:^|_)(lat|latitude)(?:$|_)")
GEO_LON_KEY_PATTERN = re.compile(r"(?:^|_)(lon|longitude)(?:$|_)")
GEO_PAIR_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def _mask_token(value: str) -> str:
    value = value.strip()
    if not value:
        return MASKED_VALUE
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _normalize_key(key: str) -> str:
    """Return a snake_case lower representation of ``key`` for comparisons."""

    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", snake)
    return snake.strip("_").lower()


def _round_coordinate(value: float) -> float:
    rounded = round(value, 1)
    if rounded == 0:
        return 0.0
    return rounded


def _coarsen_coordinate(value: Any, minimum: float, maximum: float) -> Any:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if minimum <= numeric <= maximum:
            return _round_coordinate(numeric)
        return value
    if isinstance(value, str):
        try:
            numeric = float(value.strip())
        except (TypeError, ValueError):
            return value
        if minimum <= numeric <= maximum:
            return f"{_round_coordinate(numeric):.1f}"
    return value


def _coarsen_lat_lon_string(value: str) -> str:
    match = GEO_PAIR_PATTERN.match(value)
    if not match:
        return value
    try:
        lat = float(match.group(1))
        lon = float(match.group(2))
    except (TypeError, ValueError):
        return value
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return value
    return f"{_round_coordinate(lat):.1f},{_round_coordinate(lon):.1f}"


def _apply_geolocation_policy(key: str | None, value: Any) -> Any:
    if key is None:
        if isinstance(value, str):
            return _coarsen_lat_lon_string(value)
        return value

    normalized = _normalize_key(key)

    if GEO_LAT_KEY_PATTERN.search(normalized):
        return _coarsen_coordinate(value, -90.0, 90.0)
    if GEO_LON_KEY_PATTERN.search(normalized):
        return _coarsen_coordinate(value, -180.0, 180.0)

    if normalized.startswith("geo") or "geolocation" in normalized:
        if isinstance(value, str):
            return _coarsen_lat_lon_string(value)

    if isinstance(value, str):
        return _coarsen_lat_lon_string(value)
    return value


def _sanitize_value(key: str, value: Any) -> Any:
    """Redact sensitive information and limit field size."""

    lowered = key.lower() if isinstance(key, str) else ""
    value = _apply_geolocation_policy(key if isinstance(key, str) else None, value)
    if isinstance(value, str):
        if any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
            if any(keyword in lowered for keyword in TOKEN_KEYWORDS):
                return _mask_token(value)
            return MASKED_VALUE
        if len(value) > MAX_FIELD_LENGTH:
            return value[:MAX_FIELD_LENGTH] + "…[truncated]"
        return value
    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        container = type(value)
        sanitized = [_sanitize_value(key, item) for item in value]
        if container is tuple:
            return tuple(sanitized)
        if container is set:
            return set(sanitized)
        return sanitized
    return value


class PrivacyFilter(logging.Filter):
    """Ensure sensitive headers or payloads never hit the logs."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        for key in list(record.__dict__.keys()):
            if key in {"exc_info", "exc_text", "stack_info", "msg"}:
                continue
            record.__dict__[key] = _sanitize_value(key, record.__dict__[key])
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(_sanitize_value("arg", arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: _sanitize_value(k, v) for k, v in record.args.items()}
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
        client_ip_raw = client_ip_raw_ctx_var.get(None)
        if client_ip_raw:
            record.client_ip_raw = client_ip_raw
        client_ip_anonymized = client_ip_anonymized_ctx_var.get(None)
        if client_ip_anonymized:
            record.client_ip_anonymized = client_ip_anonymized
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
        raw_ip = getattr(record, "client_ip_raw", None)
        if self.mode == "raw":
            if raw_ip:
                record.client_ip = raw_ip
            else:
                record.client_ip = original
            return True

        anonymized = getattr(record, "client_ip_anonymized", None)
        if anonymized is None and raw_ip:
            anonymized = anonymize_ip(raw_ip, mode="anonymized")
        if anonymized is not None:
            record.client_ip = anonymized
        else:
            record.client_ip = original
        return True


# ---------------------------------------------------------------------------
# ECS compatible JSON formatter
# ---------------------------------------------------------------------------

SERVICE_NAME = os.getenv("SERVICE_NAME", "zoo-tracker-api")

FIELD_MAP = {
    "request_id": "http.request.id",
    "user_id": "user.id",
    "client_ip": "client.ip",
    "http_request_method": "http.request.method",
    "url_path": "url.path",
    "url_query": "url.query",
    "http_status_code": "http.response.status_code",
    "event_duration": "event.duration",
    "user_agent": "user_agent.original",
    "event_dataset": "event.dataset",
    "event_action": "event.action",
    "event_kind": "event.kind",
    "error_stack": "error.stack",
    "error_type": "error.type",
    "error_message": "error.message",
    "change_summary": "change.summary",
    "sighting_id": "sighting.id",
    "auth_method": "authentication.method",
    "auth_failure_reason": "authentication.outcome.reason",
    "validation_error_count": "validation.error.count",
    "contact_message_length": "message.length",
    "contact_email_domain": "user.domain",
}


class ECSJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that emits ECS aligned fields."""

    def __init__(self, *args: Any, service_name: str = SERVICE_NAME, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.service_name = service_name

    def add_fields(
        self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        if "@timestamp" not in log_record:
            log_record["@timestamp"] = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()

        log_record.setdefault("log.level", record.levelname)
        log_record.setdefault("message", record.getMessage())

        dataset = getattr(record, "event_dataset", None)
        if not dataset:
            dataset = log_record.get("event.dataset")
        if not dataset:
            dataset = f"{self.service_name}.app"
        log_record["event.dataset"] = dataset

        service_name = getattr(record, "service_name", None) or log_record.get("service.name")
        log_record["service.name"] = service_name or self.service_name

        for attr, ecs_name in FIELD_MAP.items():
            value = getattr(record, attr, None)
            if value is None:
                value = log_record.get(attr)
            if value is not None:
                log_record[ecs_name] = value

        # Convert exception info into ``error.stack`` if not already provided.
        if record.exc_info and "error.stack" not in log_record:
            log_record["error.stack"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).strip()

        # Drop non-serialisable values and ``None`` entries to keep logs compact.
        keys_to_delete = []
        for key, value in log_record.items():
            if value is None:
                keys_to_delete.append(key)
            elif isinstance(value, (set, bytes)):
                log_record[key] = str(value)
        for key in keys_to_delete:
            log_record.pop(key, None)


class SecureWatchedFileHandler(WatchedFileHandler):
    """File handler enforcing restrictive file permissions."""

    def _open(self):  # noqa: D401
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:
            # Ignore permission errors on read-only filesystems.
            pass
        return stream


# ---------------------------------------------------------------------------
# Public configuration helper
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Configure structured logging for the application."""

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    json_enabled = os.getenv("LOG_JSON", "true").lower() in {"1", "true", "yes", "on"}
    log_file_primary = os.getenv("LOG_FILE")
    anon_log_file = os.getenv("LOG_FILE_ANON") or log_file_primary
    raw_log_file = os.getenv("LOG_FILE_RAW")

    formatter_name = "json" if json_enabled else "plain"

    formatters: dict[str, dict[str, Any]] = {
        "json": {
            "()": "app.logging_config.ECSJsonFormatter",
            "service_name": SERVICE_NAME,
        },
        "plain": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    }

    filters = {
        "context": {"()": "app.logging_config.RequestContextFilter"},
        "privacy": {"()": "app.logging_config.PrivacyFilter"},
        "ip_anonymized": {"()": "app.logging_config.IPOverrideFilter", "mode": "anonymized"},
        "ip_raw": {"()": "app.logging_config.IPOverrideFilter", "mode": "raw"},
    }

    handlers: dict[str, dict[str, Any]] = {
        "stdout_json": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": formatter_name,
            "filters": ["context", "privacy"],
            "stream": "ext://sys.stdout",
        }
    }

    root_handlers = ["stdout_json"]

    if anon_log_file and raw_log_file:
        if os.path.abspath(anon_log_file) == os.path.abspath(raw_log_file):
            raise ValueError(
                "LOG_FILE_ANON and LOG_FILE_RAW must point to different files"
            )

    configured_paths: set[str] = set()

    def _add_file_handler(name: str, path: str, extra_filters: list[str]) -> None:
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        if abs_path in configured_paths:
            return
        handlers[name] = {
            "class": "app.logging_config.SecureWatchedFileHandler",
            "level": log_level,
            "formatter": formatter_name,
            "filters": ["context", "privacy", *extra_filters],
            "filename": abs_path,
            "delay": True,
        }
        root_handlers.append(name)
        configured_paths.add(abs_path)

    if anon_log_file:
        _add_file_handler("file_anon", anon_log_file, ["ip_anonymized"])

    if raw_log_file:
        _add_file_handler("file_raw", raw_log_file, ["ip_raw"])

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "filters": filters,
        "handlers": handlers,
        "root": {
            "level": log_level,
            "handlers": root_handlers,
        },
        "loggers": {
            "uvicorn": {"level": "INFO", "handlers": [], "propagate": True},
            "uvicorn.error": {"level": "INFO", "handlers": [], "propagate": True},
            "uvicorn.access": {"level": "INFO", "handlers": [], "propagate": True},
            "gunicorn.error": {"level": "INFO", "handlers": [], "propagate": True},
            "gunicorn.access": {"level": "INFO", "handlers": [], "propagate": True},
            "app.audit": {"level": "INFO", "handlers": [], "propagate": True},
        },
    }

    logging.config.dictConfig(logging_config)
    logging.captureWarnings(True)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def anonymize_ip(ip: str | None, mode: str | None = None) -> str | None:
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

