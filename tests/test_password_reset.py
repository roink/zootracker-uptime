"""Tests covering the password reset flow."""

from __future__ import annotations

import hashlib
import hmac
import re

from app import models, rate_limit
from app.auth import verify_password
from app.config import TOKEN_PEPPER
from app.database import SessionLocal

from .conftest import TEST_PASSWORD, client, register_and_login


TOKEN_RE = re.compile(r"reset-password\?token=([^\s]+)")


def _capture_password_reset_email(monkeypatch):
    """Capture outgoing password reset emails for assertions."""

    sent_messages: list = []

    def _capture(*, settings, message, **kwargs):
        sent_messages.append(message)

    monkeypatch.setattr(
        "app.utils.password_reset.send_email_via_smtp",
        _capture,
    )

    return sent_messages


def _reset_password_reset_limits():
    """Clear rate limiter state between tests to avoid cross-test bleed."""

    rate_limit.password_reset_request_ip_limiter.history.clear()
    rate_limit.password_reset_request_identifier_limiter.history.clear()
    rate_limit.password_reset_token_ip_limiter.history.clear()


def _parse_token(body: str) -> str:
    match = TOKEN_RE.search(body)
    assert match, "Expected reset token in email body"
    return match.group(1)


def test_password_reset_request_sends_email(monkeypatch):
    _reset_password_reset_limits()
    client.cookies.clear()
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = client.post("/auth/password/forgot", json={"email": email})
    assert resp.status_code == 202
    assert resp.json()["detail"].startswith("If an account exists")
    assert len(sent_messages) == 1

    body = sent_messages[0].get_content()
    token = _parse_token(body)

    expected_hash = hmac.new(
        TOKEN_PEPPER.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user.id)
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.PASSWORD_RESET)
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert record is not None
        assert record.token_hash == expected_hash
        assert record.consumed_at is None


def test_password_reset_request_unknown_email_is_anonymous(monkeypatch):
    _reset_password_reset_limits()
    client.cookies.clear()
    sent_messages = _capture_password_reset_email(monkeypatch)

    resp = client.post(
        "/auth/password/forgot",
        json={"email": "missing-user@example.com"},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"].startswith("If an account exists")
    assert sent_messages == []


def test_password_reset_flow_updates_password(monkeypatch):
    _reset_password_reset_limits()
    client.cookies.clear()
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = client.post("/auth/password/forgot", json={"email": email})
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())

    new_password = "reset-me-now"
    resp = client.post(
        "/auth/password/reset",
        json={
            "token": reset_token,
            "password": new_password,
            "confirmPassword": new_password,
        },
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 2, "Expected confirmation email after reset"

    # Old password should no longer work
    old_login = client.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        data={"username": email, "password": new_password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert new_login.status_code == 200

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(new_password, user.password_hash)
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user.id)
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.PASSWORD_RESET)
            .all()
        )
        assert tokens
        assert all(token.consumed_at is not None for token in tokens)
        refresh_tokens = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.user_id == user.id)
            .all()
        )
        assert refresh_tokens
        revoked = [token for token in refresh_tokens if token.revoked_at is not None]
        assert revoked, "Expected existing sessions to be revoked"
        active = [token for token in refresh_tokens if token.revoked_at is None]
        assert len(active) <= 1
        if active:
            latest = max(refresh_tokens, key=lambda token: token.issued_at)
            assert active[0].id == latest.id
