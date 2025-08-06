import smtplib
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import rate_limit
from app.rate_limit import RateLimiter
from .conftest import client


def _dummy_smtp_factory(sent_messages):
    class DummySMTP:
        def __init__(self, host, port):
            pass

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent_messages.append(msg)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    return DummySMTP


def test_contact_sends_email_with_reply_to(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    resp = client.post(
        "/contact",
        json={"name": "Alice", "email": "a@example.com", "message": "Hello"},
    )
    assert resp.status_code == 204
    assert sent[0]["Reply-To"] == "a@example.com"
    assert sent[0]["Subject"] == "Contact form – Alice"


def test_contact_strips_html(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    resp = client.post(
        "/contact",
        json={
            "name": "Alice",
            "email": "a@example.com",
            "message": "<script>alert(1)</script>Hi<b>there</b>",
        },
    )
    assert resp.status_code == 204
    body = sent[0].get_content()
    assert "<script>" not in body and "<b>" not in body


def test_contact_uses_ssl_when_configured(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_SSL", "true")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP_SSL", _dummy_smtp_factory(sent))
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))

    def fail_smtp(*args, **kwargs):
        raise AssertionError("SMTP should not be used when SMTP_SSL=true")

    monkeypatch.setattr(smtplib, "SMTP", fail_smtp)

    resp = client.post(
        "/contact",
        json={"name": "Alice", "email": "a@example.com", "message": "Hi"},
    )
    assert resp.status_code == 204
    assert sent[0]["Subject"] == "Contact form – Alice"


def test_contact_rate_limited(monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(1, 60))
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    first = client.post(
        "/contact",
        json={"name": "Bob", "email": "b@example.com", "message": "Hi"},
    )
    assert first.status_code == 204
    second = client.post(
        "/contact",
        json={"name": "Bob", "email": "b@example.com", "message": "Hi"},
    )
    assert second.status_code == 429


def test_contact_rate_limit_response_detail(monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(1, 60))
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    client.post(
        "/contact",
        json={"name": "Bob", "email": "b@example.com", "message": "Hi"},
    )
    resp = client.post(
        "/contact",
        json={"name": "Bob", "email": "b@example.com", "message": "Hi"},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "Too Many Requests"
    assert resp.headers.get("Retry-After") is not None
    assert resp.headers.get("X-RateLimit-Remaining") == "0"


def test_contact_rate_limit_headers(monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(2, 60))
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    resp = client.post(
        "/contact",
        json={"name": "Eve", "email": "e@example.com", "message": "Hi"},
    )
    assert resp.status_code == 204
    assert resp.headers.get("X-RateLimit-Remaining") == "1"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "a@example.com", "message": "Hi"},
        {"name": "Alice", "message": "Hi"},
        {"name": "Alice", "email": "not-an-email", "message": "Hi"},
        {"name": "Alice", "email": "a@example.com", "message": ""},
        {"name": "Ali😀ce", "email": "a@example.com", "message": "Hi"},
    ],
)
def test_contact_invalid_payload(monkeypatch, payload):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    resp = client.post("/contact", json=payload)
    assert resp.status_code == 422


def test_contact_rate_limit_concurrent(monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(1, 60))
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    payload = {"name": "Bob", "email": "b@example.com", "message": "Hi"}

    def do_post():
        return client.post("/contact", json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        res = list(pool.map(lambda _: do_post(), range(2)))

    codes = sorted([r.status_code for r in res])
    assert codes == [204, 429]
