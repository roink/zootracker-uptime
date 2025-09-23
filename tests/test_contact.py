import hashlib
import hmac
import os
import smtplib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import rate_limit
from app.rate_limit import RateLimiter
from .conftest import client


DEFAULT_USER_AGENT = "pytest-agent/1.0"
CONTACT_SECRET = os.getenv("CONTACT_TOKEN_SECRET", "test-contact-secret")


def _sign(rendered_at: int, user_agent: str, nonce: str) -> str:
    payload = f"{rendered_at}|{user_agent}|{nonce}".encode("utf-8")
    return hmac.new(CONTACT_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def build_contact_payload(
    name: str = "Alice",
    email: str = "a@example.com",
    message: str = "Hello world!",
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    rendered_at: int | None = None,
    nonce: str | None = None,
):
    if rendered_at is None:
        rendered_at = int(time.time() * 1000) - 5000
    if nonce is None:
        nonce = uuid.uuid4().hex
    return {
        "name": name,
        "email": email,
        "message": message,
        "rendered_at": rendered_at,
        "client_nonce": nonce,
        "signature": _sign(rendered_at, user_agent, nonce),
    }


def post_contact(payload, *, user_agent: str = DEFAULT_USER_AGENT):
    return client.post(
        "/contact",
        json=payload,
        headers={"User-Agent": user_agent},
    )


def payload_missing_name():
    payload = build_contact_payload()
    payload.pop("name")
    return payload


def payload_missing_email():
    payload = build_contact_payload()
    payload.pop("email")
    return payload


def payload_invalid_email():
    payload = build_contact_payload()
    payload["email"] = "not-an-email"
    return payload


def payload_empty_message():
    payload = build_contact_payload()
    payload["message"] = ""
    return payload


def payload_missing_signature():
    payload = build_contact_payload()
    payload.pop("signature")
    return payload


def _dummy_smtp_factory(sent_messages):
    class DummySMTP:
        def __init__(self, *args, **kwargs):
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
    monkeypatch.delenv("SMTP_SSL", raising=False)
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    payload = build_contact_payload(
        name="Alice",
        email="a@example.com",
        message="Hello world!",
    )
    resp = post_contact(payload)
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
    monkeypatch.delenv("SMTP_SSL", raising=False)
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    payload = build_contact_payload(
        name="Alice",
        email="a@example.com",
        message="<script>alert(1)</script>Hi<b>there</b>",
    )
    resp = post_contact(payload)
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

    payload = build_contact_payload(
        name="Alice",
        email="a@example.com",
        message="Hello friends!",
    )
    resp = post_contact(payload)
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

    payload = build_contact_payload(
        name="Bob",
        email="b@example.com",
        message="Hello there!",
    )
    first = post_contact(payload)
    assert first.status_code == 204
    second = post_contact(payload)
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

    payload = build_contact_payload(
        name="Bob",
        email="b@example.com",
        message="Hello there!",
    )
    post_contact(payload)
    resp = post_contact(payload)
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

    payload = build_contact_payload(
        name="Eve",
        email="e@example.com",
        message="Hello there!",
    )
    resp = post_contact(payload)
    assert resp.status_code == 204
    assert resp.headers.get("X-RateLimit-Remaining") == "1"


@pytest.mark.parametrize(
    "payload_factory",
    [
        payload_missing_email,
        payload_missing_name,
        payload_invalid_email,
        payload_empty_message,
        payload_missing_signature,
    ],
)
def test_contact_invalid_payload(monkeypatch, payload_factory):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    resp = post_contact(payload_factory())
    assert resp.status_code == 422


def test_contact_accepts_unicode_name(monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    payload = build_contact_payload(
        name="Ali😀ce",
        message="Hello from the 🐾 team!",
    )
    resp = post_contact(payload)
    assert resp.status_code == 204


def test_contact_rejects_short_message(monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    payload = build_contact_payload(message="Too short")
    resp = post_contact(payload)
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

    def do_post():
        payload = build_contact_payload(
            name="Bob",
            email="b@example.com",
            message="Hello there!",
        )
        return post_contact(payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        res = list(pool.map(lambda _: do_post(), range(2)))

    codes = sorted([r.status_code for r in res])
    assert codes == [204, 429]
