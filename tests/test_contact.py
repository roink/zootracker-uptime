import smtplib
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import rate_limit
from app.rate_limit import RateLimiter
from .conftest import client


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
    ],
)
def test_contact_invalid_payload(monkeypatch, payload_factory):
    monkeypatch.setattr(rate_limit, "contact_limiter", RateLimiter(100, 60))
    resp = post_contact(payload_factory())
    assert resp.status_code == 422


def test_contact_strips_header_injection(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    payload = build_contact_payload(
        name="Alice\r\nBcc: attacker@example.com",
        email="a@example.com",
        message="Hello there!",
    )
    resp = post_contact(payload)
    assert resp.status_code == 204
    msg = sent[0]
    assert msg["Reply-To"] == "a@example.com"
    assert msg["Subject"] == "Contact form – AliceBcc: attacker@example.com"


def test_contact_uses_starttls_when_ssl_backend_missing(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setenv("SMTP_SSL", "true")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    payload = build_contact_payload(
        name="Fallback Test",
        email="fallback@example.com",
        message="Hello there!",
    )

    resp = post_contact(payload)
    assert resp.status_code == 204
    assert sent, "Expected email to be queued via STARTTLS fallback"
    assert sent[0]["Subject"] == "Contact form – Fallback Test"


def test_send_contact_email_sanitizes_reply_to(monkeypatch):
    sent = []

    def smtp_factory(*args, **kwargs):
        return _dummy_smtp_factory(sent)(*args, **kwargs)

    monkeypatch.setattr(smtplib, "SMTP", smtp_factory)
    monkeypatch.setattr(smtplib, "SMTP_SSL", smtp_factory)

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

    assert sent, "Expected email to be queued"
    msg = sent[0]
    header_value = msg["Reply-To"]
    assert "\r" not in header_value and "\n" not in header_value
    assert header_value.startswith("a@example.com")
    assert "attacker@example.com" not in header_value
    assert msg["Subject"] == "Contact form – Alice"


def test_contact_sets_request_id_header(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "contact@zootracker.app")
    monkeypatch.setenv("CONTACT_EMAIL", "contact@zootracker.app")
    monkeypatch.setattr(smtplib, "SMTP", _dummy_smtp_factory(sent))

    resp = post_contact(build_contact_payload())
    assert resp.status_code == 204
    assert "X-Request-ID" in resp.headers


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
