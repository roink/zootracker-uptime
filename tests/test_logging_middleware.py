import logging

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app import logging_config
from app.logging_config import configure_logging
from app.middleware.logging import LoggingMiddleware


@pytest.fixture(autouse=True)
def configure_logs(monkeypatch):
    monkeypatch.setenv("ACCESS_LOG_SAMPLE", "1.0")
    monkeypatch.setenv("SLOW_REQUEST_MS", "1000")
    configure_logging()


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/ok")
    async def ok_endpoint():  # pragma: no cover - exercised via TestClient
        return {"status": "ok"}

    @app.get("/warn")
    async def warn_endpoint():  # pragma: no cover - exercised via TestClient
        raise HTTPException(status_code=400, detail="bad request")

    @app.get("/boom")
    async def boom_endpoint():  # pragma: no cover - exercised via TestClient
        raise RuntimeError("explode")

    @app.get("/auth")
    async def auth_endpoint(request: Request):  # pragma: no cover
        logging.getLogger("app.test").info(
            "Auth header check",
            extra={"authorization": request.headers.get("Authorization", "")},
        )
        return {"ok": True}

    return app


def test_logging_middleware_records_duration_and_request_id(caplog):
    app = create_app()
    client = TestClient(app)
    caplog.set_level(logging.INFO)

    response = client.get("/ok", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"

    record = next(r for r in caplog.records if r.message.startswith("GET /ok"))
    assert getattr(record, "event_duration") > 0
    assert getattr(record, "request_id") == "req-123"
    assert getattr(record, "http_status_code") == 200
    assert getattr(record, "client_ip") == "unknown"
    assert getattr(record, "client_ip_raw") == "unknown"
    assert getattr(record, "client_ip_anonymized") == "unknown"


def test_logging_middleware_emits_warning_for_client_errors(caplog):
    app = create_app()
    client = TestClient(app)
    caplog.set_level(logging.INFO)
    caplog.clear()

    response = client.get("/warn")
    assert response.status_code == 400

    record = next(r for r in caplog.records if r.message.startswith("GET /warn"))
    assert record.levelno == logging.WARNING


def test_logging_middleware_emits_error_for_server_errors(caplog):
    app = create_app()
    client = TestClient(app)
    caplog.set_level(logging.INFO)
    caplog.clear()

    with pytest.raises(RuntimeError):
        client.get("/boom")

    record = next(r for r in caplog.records if r.message.startswith("GET /boom"))
    assert record.levelno == logging.ERROR
    assert "error_stack" in record.__dict__


def test_authorization_header_redacted(caplog):
    app = create_app()
    client = TestClient(app)
    caplog.set_level(logging.INFO)
    caplog.clear()

    client.get("/auth", headers={"Authorization": "Bearer top-secret-token"})

    header_record = next(r for r in caplog.records if r.name == "app.test")
    assert getattr(header_record, "authorization") != "Bearer top-secret-token"
    assert "top-secret-token" not in caplog.text


def test_geolocation_values_are_coarsened(caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()
    logger = logging.getLogger("app.geo")

    logger.info(
        "geo precision",
        extra={
            "user_latitude": 48.8566,
            "userLongitude": 2.3522,
            "geo_location": "48.8566, 2.3522",
            "user_location": "48.8566, 2.3522",
        },
    )

    record = next(r for r in caplog.records if r.message == "geo precision")
    assert getattr(record, "user_latitude") == pytest.approx(48.9)
    assert getattr(record, "userLongitude") == pytest.approx(2.4)
    assert getattr(record, "geo_location") == "48.9,2.4"
    assert getattr(record, "user_location") == "48.9,2.4"


def test_ip_override_filter_modes():
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="sample",
        args=(),
        exc_info=None,
    )
    record.client_ip = "unknown"
    record.client_ip_raw = "198.51.100.23"
    record.client_ip_anonymized = None

    anon_filter = logging_config.IPOverrideFilter("anonymized")
    raw_filter = logging_config.IPOverrideFilter("raw")

    anon_filter.filter(record)
    assert record.client_ip == "198.51.100.0/24"

    raw_filter.filter(record)
    assert record.client_ip == "198.51.100.23"
