import json
import logging
from urllib.parse import parse_qsl

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app import logging as app_logging
from app.logging import configure_logging
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
    assert not hasattr(record, "client_ip_raw")
    assert not hasattr(record, "client_ip_anonymized")


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


async def test_sensitive_header_dictionary_entries_redacted(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()
    logger = logging.getLogger("app.headers")

    logger.info(
        "header audit",
        extra={
            "headers": {
                "X-Api-Key": "abcd1234secret5678",
                "Proxy-Authorization": "Basic super-secret-key",
                "X-Csrf-Token": "csrfsecretvalue",
            }
        },
    )

    record = next(r for r in caplog.records if r.message == "header audit")
    headers = record.headers
    assert headers["X-Api-Key"] != "abcd1234secret5678"
    assert "secret" not in headers["X-Api-Key"]
    assert headers["Proxy-Authorization"] != "Basic super-secret-key"
    assert "super-secret" not in headers["Proxy-Authorization"]
    assert headers["X-Csrf-Token"] != "csrfsecretvalue"
    assert "csrfsecretvalue" not in headers["X-Csrf-Token"]
    assert "secret" not in caplog.text


async def test_geolocation_values_are_coarsened(client, caplog):
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


async def test_url_query_coordinates_are_coarsened(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()
    logger = logging.getLogger("app.geo")

    logger.info(
        "geo query",
        extra={
            "url_query": "latitude=50.9607936&longitude=6.9238784&"
            "q=50.9607936,6.9238784&limit=20",
        },
    )

    record = next(r for r in caplog.records if r.message == "geo query")
    parsed = dict(parse_qsl(getattr(record, "url_query")))
    assert parsed["latitude"] == "51.0"
    assert parsed["longitude"] == "6.9"
    assert parsed["q"] == "51.0,6.9"
    assert parsed["limit"] == "20"


async def test_ip_override_filter_modes(client):
    raw_ip = "198.51.100.23"
    tokens = app_logging.bind_request_context(
        request_id="req-ctx",
        client_ip=raw_ip,
        client_ip_raw=raw_ip,
        client_ip_anonymized=app_logging.anonymize_ip(raw_ip, mode="anonymized"),
    )

    try:
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="sample",
            args=(),
            exc_info=None,
        )
        record.client_ip = raw_ip

        anon_filter = app_logging.IPOverrideFilter("anonymized")
        raw_filter = app_logging.IPOverrideFilter("raw")

        anon_filter.filter(record)
        assert record.client_ip == "198.51.100.0/24"
        assert not hasattr(record, "client_ip_raw")

        raw_filter.filter(record)
        assert record.client_ip == raw_ip
    finally:
        app_logging.reset_request_context(tokens)


async def test_ecs_formatter_deduplicates_fields_and_sanitizes_query(client):
    formatter = app_logging.ECSJsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="GET /animals -> 200",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    record.client_ip = "198.51.100.0/24"
    record.client_ip_raw = "198.51.100.23"
    record.client_ip_anonymized = "198.51.100.0/24"
    record.url_query = "latitude=50.9607936&longitude=6.9238784"
    record.user_agent = "Mozilla/5.0"
    record.http_request_method = "GET"
    record.url_path = "/animals"
    record.http_status_code = 200
    record.event_duration = 123_456
    record.event_dataset = "zoo-tracker-api.access"

    privacy_filter = app_logging.PrivacyFilter()
    assert privacy_filter.filter(record)

    payload = json.loads(formatter.format(record))

    for alias in app_logging.FIELD_MAP:
        assert alias not in payload
    assert "client_ip_raw" not in payload
    assert "client_ip_anonymized" not in payload
    assert payload["client.ip"] == "198.51.100.0/24"
    assert payload["http.request.id"] == "req-1"
    assert payload["event.dataset"] == "zoo-tracker-api.access"
    parsed_query = dict(parse_qsl(payload["url.query"]))
    assert parsed_query["latitude"] == "51.0"
    assert parsed_query["longitude"] == "6.9"
