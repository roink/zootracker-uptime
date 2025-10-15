import re
import uuid
from datetime import timedelta

from app import models
from app.database import SessionLocal

from .conftest import CONSENT_VERSION, TEST_PASSWORD, client

TOKEN_RE = re.compile(r"token=([^\s]+)")
CODE_RE = re.compile(r"code: (\d{6,8})", re.IGNORECASE)


def _register_user(monkeypatch, *, email: str | None = None):
    """Create a user and capture the verification email."""

    sent_messages = []

    def _capture_email(*, settings, message, **kwargs):
        sent_messages.append(message)

    monkeypatch.setattr(
        "app.utils.email_sender.send_email_via_smtp",
        _capture_email,
    )
    monkeypatch.setattr(
        "app.utils.email_verification.send_email_via_smtp",
        _capture_email,
    )

    addr = email or f"verify-{uuid.uuid4()}@example.com"
    resp = client.post(
        "/users",
        json={
            "name": "Verifier",
            "email": addr,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 200
    assert sent_messages, "Expected verification email to be sent"
    return resp.json(), sent_messages


def _parse_token(body: str) -> str:
    match = TOKEN_RE.search(body)
    assert match, "Expected token in email body"
    return match.group(1)


def _parse_code(body: str) -> str:
    match = CODE_RE.search(body)
    assert match, "Expected numeric code in email body"
    return match.group(1)


def test_signup_triggers_verification_email(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    body = messages[0].get_content()
    assert user_info["email"].lower() in body.lower()
    assert "verification" in body.lower()
    assert "verify?uid=" in body
    assert _parse_token(body)
    assert _parse_code(body)


def test_resend_respects_cooldown(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)

    resp = client.post(
        "/auth/login",
        data={"username": user_info["email"], "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]

    with SessionLocal() as db:
        user = db.get(models.User, user_info["id"])
        user.last_verify_sent_at = user.last_verify_sent_at - timedelta(minutes=2)
        user.verify_attempts = 1
        db.commit()

    resp = client.post(
        "/auth/verification/resend",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 202

    resp = client.post(
        "/auth/verification/resend",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 429


def test_verify_email_with_token(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    resp = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert resp.status_code == 200

    with SessionLocal() as db:
        user = db.get(models.User, user_info["id"])
        assert user.email_verified_at is not None
        assert user.verify_token_hash is None
        assert user.verify_code_hash is None


def test_verify_email_with_code(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    code = _parse_code(messages[0].get_content())

    resp = client.post(
        "/auth/verify",
        json={"email": user_info["email"], "code": code},
    )
    assert resp.status_code == 200

    with SessionLocal() as db:
        user = db.get(models.User, user_info["id"])
        assert user.email_verified_at is not None
