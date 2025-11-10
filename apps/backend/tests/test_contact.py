import smtplib

import pytest

from app import rate_limit
from app.rate_limit import RateLimiter



DEFAULT_USER_AGENT = "pytest-agent/1.0"


def build_contact_payload(
    name: str = "Alice",
    email: str = "a@example.com",
    message: str = "Hello world!",
):
    return {
        "name": name,
        "email": email,
        "message": message,
    }


async def post_contact(client, payload, *, user_agent: str = DEFAULT_USER_AGENT):
    return await client.post(
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


def _dummy_smtp_factory(sent_messages):
    class DummySMTP:
        def __init__(self, *args, **kwargs):
            pass

        def starttls(self, *args, **kwargs):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent_messages.append(msg)

        def ehlo(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    return DummySMTP


async def test_contact_sends_email_with_reply_to(client, monkeypatch, fake_email_sender):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")

    payload = build_contact_payload(
        name="Alice",
        email="a@example.com",
        message="Hello world!",
    )
    resp = await post_contact(client, payload)
    assert resp.status_code == 204
    assert len(fake_email_sender.outbox) == 1
    email = fake_email_sender.outbox[0]
    assert email["reply_to"] == "a@example.com"
    assert email["subject"] == "Contact form – Alice"


async def test_contact_strips_html(client, monkeypatch, fake_email_sender):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")

    payload = build_contact_payload(
        name="Alice",
        email="a@example.com",
        message="<script>alert(1)</script>Hi<b>there</b>",
    )
    resp = await post_contact(client, payload)
    assert resp.status_code == 204
    assert len(fake_email_sender.outbox) == 1
    body = fake_email_sender.outbox[0]["body"]
    assert "<script>" not in body and "<b>" not in body


async def test_contact_uses_ssl_when_configured(client, monkeypatch, fake_email_sender):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_SSL", "true")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))

    payload = build_contact_payload(
        name="Alice",
        email="a@example.com",
        message="Hello friends!",
    )
    resp = await post_contact(client, payload)
    assert resp.status_code == 204
    assert len(fake_email_sender.outbox) == 1
    assert fake_email_sender.outbox[0]["subject"] == "Contact form – Alice"


async def test_contact_rate_limited(client, monkeypatch):
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
    first = await post_contact(client, payload)
    assert first.status_code == 204
    second = await post_contact(client, payload)
    assert second.status_code == 429


async def test_contact_rate_limit_response_detail(client, monkeypatch):
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
    await post_contact(client, payload)
    resp = await post_contact(client, payload)
    assert resp.status_code == 429
    assert resp.json()["detail"] == "Too Many Requests"
    assert resp.headers.get("Retry-After") is not None
    assert resp.headers.get("X-RateLimit-Remaining") == "0"


async def test_contact_rate_limit_headers(client, monkeypatch):
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
    resp = await post_contact(client, payload)
    assert resp.status_code == 204
    assert resp.headers.get("X-RateLimit-Remaining") == "1"


@pytest.mark.parametrize(
    "payload_factory",
    [
        payload_missing_email,
        payload_missing_name,
        payload_invalid_email,
        payload_empty_message,
    ],
)
async def test_contact_invalid_payload(client, monkeypatch, payload_factory):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    resp = await post_contact(client, payload_factory())
    assert resp.status_code == 422


async def test_contact_strips_header_injection(client, monkeypatch, fake_email_sender):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")

    payload = build_contact_payload(
        name="Alice\r\nBcc: attacker@example.com",
        email="a@example.com",
        message="Hello there!",
    )
    resp = await post_contact(client, payload)
    assert resp.status_code == 204
    assert len(fake_email_sender.outbox) == 1
    email = fake_email_sender.outbox[0]
    assert email["reply_to"] == "a@example.com"
    assert email["subject"] == "Contact form – AliceBcc: attacker@example.com"


async def test_contact_uses_starttls_when_ssl_backend_missing(client, monkeypatch, fake_email_sender):
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setenv("SMTP_SSL", "true")

    payload = build_contact_payload(
        name="Fallback Test",
        email="fallback@example.com",
        message="Hello there!",
    )

    resp = await post_contact(client, payload)
    assert resp.status_code == 204
    assert len(fake_email_sender.outbox) == 1, "Expected email to be queued"
    assert fake_email_sender.outbox[0]["subject"] == "Contact form – Fallback Test"


async def test_send_contact_email_sanitizes_reply_to(fake_email_sender):
    from app.api.contact import _send_contact_email

    _send_contact_email(
        host="smtp.test",
        port=587,
        use_ssl=False,
        user="",
        password="",
        from_addr="contact@zootracker.app",
        to_addr="contact@zootracker.app",
        reply_to="a@example.com\r\nBcc: attacker@example.com",
        name="Alice",
        msg_text="Hello there!",
    )

    assert len(fake_email_sender.outbox) == 1, "Expected email to be queued"
    email = fake_email_sender.outbox[0]
    header_value = email["reply_to"]
    assert "\r" not in header_value and "\n" not in header_value
    assert header_value.startswith("a@example.com")
    assert "attacker@example.com" not in header_value
    assert email["subject"] == "Contact form – Alice"


async def test_contact_sets_request_id_header(client, monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    resp = await post_contact(client, build_contact_payload())
    assert resp.status_code == 204
    assert "X-Request-ID" in resp.headers


async def test_contact_accepts_unicode_name(client, monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    payload = build_contact_payload(
        name="Ali😀ce",
        message="Hello from the 🐾 team!",
    )
    resp = await post_contact(client, payload)
    assert resp.status_code == 204


async def test_contact_rejects_short_message(client, monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    payload = build_contact_payload(message="Too short")
    resp = await post_contact(client, payload)
    assert resp.status_code == 422
import asyncio


async def test_contact_rate_limit_concurrent(client, monkeypatch):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(1, 60))
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    async def do_post():
        payload = build_contact_payload(
            name="Bob",
            email="b@example.com",
            message="Hello there!",
        )
        return await post_contact(client, payload)

    res = await asyncio.gather(*(do_post() for _ in range(2)))

    codes = sorted([r.status_code for r in res])
    assert codes == [204, 429]
