"""Request/response logging middleware that emits structured JSON logs."""

from __future__ import annotations

import logging
import os
import random
import time
import traceback
import uuid

from fastapi import HTTPException, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ..logging import (
    anonymize_ip,
    bind_request_context,
    reset_request_context,
    set_user_context,  # re-exported for convenience
)
from ..utils.network import get_client_ip as resolve_client_ip


def _load_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
        if parsed < 0:
            return default
        return parsed
    except ValueError:
        return default


class LoggingMiddleware(BaseHTTPMiddleware):
    """Emit ECS compatible JSON access logs for every request."""

    noise_paths = {"/health", "/healthz", "/ready", "/live"}

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("app.access")
        self.sample_rate = max(0.0, min(1.0, _load_float_env("ACCESS_LOG_SAMPLE", 1.0)))
        slow_ms = _load_float_env("SLOW_REQUEST_MS", 500.0)
        self.slow_request_ns = int(slow_ms * 1_000_000)
        self.random = random.SystemRandom()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_ns = time.perf_counter_ns()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip_raw = resolve_client_ip(request)
        client_ip_logged = anonymize_ip(client_ip_raw)
        client_ip_anonymized = anonymize_ip(client_ip_raw, mode="anonymized")
        request.state.client_ip = client_ip_raw
        request.state.client_ip_logged = client_ip_logged
        request.state.client_ip_anonymized = client_ip_anonymized

        tokens = bind_request_context(
            request_id=request_id,
            client_ip=client_ip_logged,
            client_ip_raw=client_ip_raw,
            client_ip_anonymized=client_ip_anonymized,
        )

        status_code = 500
        response: Response | None = None
        error_type: str | None = None
        error_message: str | None = None
        error_stack: str | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except (HTTPException, StarletteHTTPException) as exc:
            status_code = exc.status_code
            error_type = type(exc).__name__
            detail = getattr(exc, "detail", None)
            if isinstance(detail, str):
                error_message = detail
            raise
        except Exception as exc:  # noqa: BLE001 - log unexpected errors
            status_code = 500
            error_type = type(exc).__name__
            error_message = str(exc)
            error_stack = "".join(
                traceback.format_exception(exc.__class__, exc, exc.__traceback__)
            )
            raise
        finally:
            duration_ns = time.perf_counter_ns() - start_ns
            request.state.event_duration_ns = duration_ns

            should_log = self._should_log(request, status_code, duration_ns)
            if should_log:
                log_level = logging.INFO
                if status_code >= 500:
                    log_level = logging.ERROR
                elif status_code >= 400:
                    log_level = logging.WARNING

                query = request.url.query or None
                user_agent = request.headers.get("User-Agent") or None
                message = f"{request.method} {request.url.path} -> {status_code}"
                extra = {
                    "http_request_method": request.method,
                    "url_path": request.url.path,
                    "url_query": query,
                    "http_status_code": status_code,
                    "event_duration": duration_ns,
                    "client_ip": client_ip_logged,
                    "user_agent": user_agent,
                    "event_dataset": "zoo-tracker-api.access",
                }
                if duration_ns >= self.slow_request_ns:
                    extra["event_action"] = "slow_request"
                if error_type:
                    extra["error_type"] = error_type
                if error_message:
                    extra["error_message"] = error_message
                if error_stack:
                    extra["error_stack"] = error_stack

                self.logger.log(log_level, message, extra=extra)

            reset_request_context(tokens)

    def _should_log(self, request: Request, status_code: int, duration_ns: int) -> bool:
        if request.url.path in self.noise_paths and status_code < 400:
            return False
        if status_code >= 400:
            return True
        if duration_ns >= self.slow_request_ns:
            return True
        if self.sample_rate >= 1.0:
            return True
        return self.random.random() < self.sample_rate


__all__ = ["LoggingMiddleware", "set_user_context"]

