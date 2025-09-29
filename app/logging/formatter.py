"""Custom JSON formatter compatible with ECS."""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any

from pythonjsonlogger import jsonlogger

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
            value = log_record.pop(attr, getattr(record, attr, None))
            if value is not None:
                log_record[ecs_name] = value

        for transient in {"client_ip_raw", "client_ip_anonymized"}:
            log_record.pop(transient, None)

        if record.exc_info and "error.stack" not in log_record:
            log_record["error.stack"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).strip()

        keys_to_delete = []
        for key, value in log_record.items():
            if value is None:
                keys_to_delete.append(key)
            elif isinstance(value, (set, bytes)):
                log_record[key] = str(value)
        for key in keys_to_delete:
            log_record.pop(key, None)
