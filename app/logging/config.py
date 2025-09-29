"""Public entry point for configuring application logging."""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any

from .filters import IPOverrideFilter, PrivacyFilter, RequestContextFilter
from .formatter import ECSJsonFormatter, SERVICE_NAME
from .handlers import SecureWatchedFileHandler


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
            "()": "app.logging.formatter.ECSJsonFormatter",
            "service_name": SERVICE_NAME,
        },
        "plain": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    }

    filters = {
        "context": {"()": "app.logging.filters.RequestContextFilter"},
        "privacy": {"()": "app.logging.filters.PrivacyFilter"},
        "ip_anonymized": {"()": "app.logging.filters.IPOverrideFilter", "mode": "anonymized"},
        "ip_raw": {"()": "app.logging.filters.IPOverrideFilter", "mode": "raw"},
    }

    handlers: dict[str, dict[str, Any]] = {
        "stdout_json": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": formatter_name,
            "filters": ["context", "privacy", "ip_anonymized"],
            "stream": "ext://sys.stdout",
        }
    }

    root_handlers = ["stdout_json"]

    if anon_log_file and raw_log_file:
        if os.path.abspath(anon_log_file) == os.path.abspath(raw_log_file):
            raise ValueError("LOG_FILE_ANON and LOG_FILE_RAW must point to different files")

    configured_paths: set[str] = set()

    def _add_file_handler(name: str, path: str, extra_filters: list[str]) -> None:
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        if abs_path in configured_paths:
            return
        handlers[name] = {
            "class": "app.logging.handlers.SecureWatchedFileHandler",
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
