"""Tests covering the password reset flow."""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app import models, rate_limit
from app.api import auth as auth_api
from app.auth import hash_refresh_token, verify_password
from app.config import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFERRER_POLICY,
    REFRESH_COOKIE_NAME,
    TOKEN_PEPPER,
)
from app.database import SessionLocal

from .conftest import TEST_PASSWORD, register_and_login, get_client


RESET_URL_RE = re.compile(r"https?://[^\s>\"']+/reset-password[^\s>\"']*")


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
    rate_limit.password_reset_token_identifier_limiter.history.clear()
    rate_limit.password_reset_failed_ip_limiter.history.clear()
    rate_limit.password_reset_failed_identifier_limiter.history.clear()
    auth_api._failure_attempts.clear()


@pytest.fixture(autouse=True)
def reset_password_state():
    _reset_password_reset_limits()
    try:
        client = get_client()
    except RuntimeError:
        client = None
    else:
        client.cookies.clear()
    yield
    _reset_password_reset_limits()
    if client is not None:
        client.cookies.clear()


def _parse_token(body: str) -> str:
    for match in RESET_URL_RE.findall(body):
        parsed = urlparse(match)
        token_values = parse_qs(parsed.query).get("token")
        if token_values and token_values[0]:
            return token_values[0]
    raise AssertionError("Expected reset token in email body")


def _get_latest_reset_token(db: Session, user_id):
    return (
        db.query(models.VerificationToken)
        .filter(models.VerificationToken.user_id == user_id)
        .filter(models.VerificationToken.kind == models.VerificationTokenKind.PASSWORD_RESET)
        .order_by(models.VerificationToken.created_at.desc())
        .first()
    )


async def _attempt_refresh_with_cookies(refresh_value: str, csrf_value: str):
    client = get_client()
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE_NAME, refresh_value)
    client.cookies.set(CSRF_COOKIE_NAME, csrf_value)
    return await client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_value},
    )


def _hash_token(raw: str) -> str:
    return hmac.new(
        TOKEN_PEPPER.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _assert_sensitive_headers(response):
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("Pragma") == "no-cache"
    expected_policy = REFERRER_POLICY or "no-referrer"
    assert response.headers.get("Referrer-Policy") == expected_policy


async def _post_password_forgot(*, email: str):
    client = get_client()
    response = await client.post("/auth/password/forgot", json={"email": email})
    _assert_sensitive_headers(response)
    return response


async def _post_password_reset(payload: dict[str, str]):
    client = get_client()
    response = await client.post("/auth/password/reset", json=payload)
    _assert_sensitive_headers(response)
    return response


async def _get_password_reset_status(token: str):
    client = get_client()
    response = await client.get(
        "/auth/password/reset/status",
        params={"token": token},
    )
    _assert_sensitive_headers(response)
    return response


async def test_password_reset_request_rate_limited_returns_generic_payload(client, monkeypatch):
    async def _raise_rate_limit(*_args, **_kwargs):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS)

    monkeypatch.setattr(
        auth_api,
        "enforce_password_reset_request_limit",
        _raise_rate_limit,
    )

    resp = await _post_password_forgot(email="rate-limited@example.com")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert resp.json() == {
        "detail": "If an account exists for that email, we'll send password reset instructions shortly.",
    }


async def test_password_reset_submission_rate_limited_returns_generic_payload(client, monkeypatch):
    async def _raise_rate_limit(*_args, **_kwargs):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS)

    monkeypatch.setattr(
        auth_api,
        "enforce_password_reset_token_limit",
        _raise_rate_limit,
    )

    payload = {
        "token": "rate-limited-token",
        "password": "RateLimitPass1!",
        "confirmPassword": "RateLimitPass1!",
    }

    resp = await _post_password_reset(payload)
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert resp.json() == {
        "detail": "If the reset token is valid, your password has been updated.",
        "status": "rate_limited",
    }


async def test_password_reset_status_rate_limited_returns_generic_payload(client, monkeypatch):
    async def _raise_rate_limit(*_args, **_kwargs):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS)

    monkeypatch.setattr(
        auth_api,
        "enforce_password_reset_token_limit",
        _raise_rate_limit,
    )

    resp = await _get_password_reset_status("rate-limited-token")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert resp.json() == {
        "detail": "If the reset token is valid, your password has been updated.",
        "status": "rate_limited",
    }


async def test_password_reset_request_sends_email(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert resp.json()["detail"].startswith("If an account exists")
    assert len(sent_messages) == 1

    body = sent_messages[0].get_content()
    token = _parse_token(body)

    expected_hash = _hash_token(token)

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


async def test_password_reset_request_unknown_email_is_anonymous(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    resp = await _post_password_forgot(email="missing-user@example.com")
    assert resp.status_code == 202
    assert resp.json()["detail"].startswith("If an account exists")
    assert sent_messages == []


async def test_password_reset_flow_updates_password(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]
    user_uuid = uuid.UUID(user_id)

    first_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    first_csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert first_refresh and first_csrf, "Expected refresh cookies after initial login"
    first_refresh_hash = hash_refresh_token(first_refresh)

    client.cookies.clear()
    second_login = await client.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "user-agent": "second-device",
        },
    )
    assert second_login.status_code == 200
    second_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    second_csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert second_refresh and second_csrf, "Expected refresh cookies for second session"
    second_refresh_hash = hash_refresh_token(second_refresh)

    with SessionLocal() as db:
        active_sessions = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.user_id == user_uuid)
            .filter(models.RefreshToken.revoked_at.is_(None))
            .count()
        )
    assert active_sessions == 2, "Both sessions should be active before the reset"

    client.cookies.clear()
    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())

    new_password = "reset-me-now"
    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": new_password,
            "confirmPassword": new_password,
        }
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 2, "Expected confirmation email after reset"

    # Old password should no longer work
    old_login = await client.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login",
        data={"username": email, "password": new_password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert new_login.status_code == 200

    with SessionLocal() as db:
        user = db.get(models.User, user_uuid)
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
        tokens_by_hash = {token.token_hash: token for token in refresh_tokens}
        assert first_refresh_hash in tokens_by_hash
        assert second_refresh_hash in tokens_by_hash
        assert tokens_by_hash[first_refresh_hash].revoked_at is not None
        assert tokens_by_hash[first_refresh_hash].revocation_reason == "password_reset"
        assert tokens_by_hash[second_refresh_hash].revoked_at is not None
        assert tokens_by_hash[second_refresh_hash].revocation_reason == "password_reset"
        active_tokens = [token for token in refresh_tokens if token.revoked_at is None]
        assert active_tokens
        for active in active_tokens:
            assert active.token_hash not in {first_refresh_hash, second_refresh_hash}

    first_refresh_resp = await _attempt_refresh_with_cookies(first_refresh, first_csrf)
    assert first_refresh_resp.status_code == 401
    assert first_refresh_resp.json()["detail"] == "Refresh token revoked"

    second_refresh_resp = await _attempt_refresh_with_cookies(second_refresh, second_csrf)
    assert second_refresh_resp.status_code == 401
    assert second_refresh_resp.json()["detail"] == "Refresh token revoked"

    client.cookies.clear()


async def test_password_reset_invalid_token_backoff(client, monkeypatch):
    _capture_password_reset_email(monkeypatch)

    # Issue a real reset to ensure baseline state but discard the token.
    _token, _user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]
    await _post_password_forgot(email=email)

    limit = rate_limit.PASSWORD_RESET_FAILED_IP_LIMIT
    for attempt in range(limit):
        token = f"invalid-token-{attempt}"
        resp = await _post_password_reset(
            {
                "token": token,
                "password": "Another-pass1",
                "confirmPassword": "Another-pass1",
            }
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert body["status"] == "invalid"
        assert "Request a new password reset email" in body["detail"]

    resp = await _post_password_reset(
        {
            "token": "invalid-token-final",
            "password": "Another-pass1",
            "confirmPassword": "Another-pass1",
        }
    )
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = resp.json()
    assert data["detail"].startswith("If the reset token is valid")
    assert data["status"] == "rate_limited"


async def test_password_reset_status_invalid_token_backoff(client, monkeypatch):
    _capture_password_reset_email(monkeypatch)

    # Issue a real reset to ensure baseline state but discard the token.
    _token, _user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]
    await _post_password_forgot(email=email)

    limit = rate_limit.PASSWORD_RESET_FAILED_IP_LIMIT
    for attempt in range(limit):
        token = f"invalid-status-token-{attempt}"
        resp = await _get_password_reset_status(token)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert body["status"] == "invalid"
        assert "Request a new password reset email" in body["detail"]

    resp = await _get_password_reset_status("invalid-status-token-final")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = resp.json()
    assert data["detail"].startswith("If the reset token is valid")
    assert data["status"] == "rate_limited"


async def test_password_reset_token_cannot_be_used_after_expiration(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())

    with SessionLocal() as db:
        record = _get_latest_reset_token(db, user_id)
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()

    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": "ExpiredPass1!",
            "confirmPassword": "ExpiredPass1!",
        }
    )
    assert resp.status_code == status.HTTP_410_GONE
    body = resp.json()
    assert body["status"] == "expired"
    assert "Request a new password reset email" in body["detail"]
    assert len(sent_messages) == 1

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(TEST_PASSWORD, user.password_hash)
        assert not verify_password("ExpiredPass1!", user.password_hash)
        record = _get_latest_reset_token(db, user_id)
        assert record is not None
        assert record.consumed_at is None


async def test_password_reset_token_is_single_use(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())

    first_password = "SingleUsePass1!"
    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": first_password,
            "confirmPassword": first_password,
        }
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 2

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(first_password, user.password_hash)
        record = _get_latest_reset_token(db, user_id)
        assert record is not None
        first_consumed_at = record.consumed_at
        assert first_consumed_at is not None

    second_password = "AnotherReset2!"
    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": second_password,
            "confirmPassword": second_password,
        }
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    body = resp.json()
    assert body["status"] == "consumed"
    assert "Request a new password reset email" in body["detail"]
    assert len(sent_messages) == 2

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(first_password, user.password_hash)
        assert not verify_password(second_password, user.password_hash)
        record = _get_latest_reset_token(db, user_id)
        assert record is not None
        assert record.consumed_at == first_consumed_at


async def test_password_reset_new_request_invalidates_previous_token(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    current_time = datetime.now(UTC)

    def _fake_now() -> datetime:
        return current_time

    monkeypatch.setattr("app.utils.password_reset._now", _fake_now)

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1
    token_one = _parse_token(sent_messages[0].get_content())

    current_time = current_time + timedelta(seconds=2)

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 2
    token_two = _parse_token(sent_messages[1].get_content())

    first_hash = _hash_token(token_one)
    second_hash = _hash_token(token_two)

    with SessionLocal() as db:
        first_record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user_id)
            .filter(models.VerificationToken.token_hash == first_hash)
            .first()
        )
        second_record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user_id)
            .filter(models.VerificationToken.token_hash == second_hash)
            .first()
        )
        assert first_record is not None
        assert second_record is not None
        first_consumed_at = first_record.consumed_at
        assert first_consumed_at is not None
        assert second_record.consumed_at is None
        assert verify_password(TEST_PASSWORD, second_record.user.password_hash)

    resp = await _post_password_reset(
        {
            "token": token_one,
            "password": "IgnoredPass1!",
            "confirmPassword": "IgnoredPass1!",
        }
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    body = resp.json()
    assert body["status"] == "consumed"
    assert "Request a new password reset email" in body["detail"]
    assert len(sent_messages) == 2

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(TEST_PASSWORD, user.password_hash)
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user_id)
            .filter(models.VerificationToken.token_hash == first_hash)
            .first()
        )
        assert record is not None
        assert record.consumed_at == first_consumed_at

    new_password = "ValidSecondPass1!"
    resp = await _post_password_reset(
        {
            "token": token_two,
            "password": new_password,
            "confirmPassword": new_password,
        }
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 3

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(new_password, user.password_hash)
        second_record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user_id)
            .filter(models.VerificationToken.token_hash == second_hash)
            .first()
        )
        assert second_record is not None
        assert second_record.consumed_at is not None


async def test_password_reset_status_endpoint_reports_consumed_token(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())

    status_resp = await _get_password_reset_status(reset_token)
    assert status_resp.status_code == status.HTTP_200_OK
    assert status_resp.json() == {"status": "valid"}

    new_password = "StatusCheckPass1!"
    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": new_password,
            "confirmPassword": new_password,
        }
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 2

    status_resp = await _get_password_reset_status(reset_token)
    assert status_resp.status_code == status.HTTP_409_CONFLICT
    consumed_body = status_resp.json()
    assert consumed_body["status"] == "consumed"
    assert "already been used" in consumed_body["detail"]


async def test_password_reset_status_endpoint_handles_invalid_token(client):
    resp = await _get_password_reset_status("does-not-exist")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    assert body["status"] == "invalid"
    assert "Request a new password reset email" in body["detail"]


async def test_password_reset_status_reports_missing_user(client, monkeypatch):
    future = datetime.now(UTC) + timedelta(minutes=5)
    token_record = SimpleNamespace(
        consumed_at=None,
        expires_at=future,
        user=None,
        user_id=uuid.uuid4(),
    )

    monkeypatch.setattr(
        auth_api,
        "get_reset_token",
        lambda _db, token: token_record,
    )

    resp = await _get_password_reset_status("token-without-user")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    assert body["status"] == "invalid"
    assert "Request a new password reset email" in body["detail"]


async def test_password_reset_submission_reports_missing_user(client, monkeypatch):
    future = datetime.now(UTC) + timedelta(minutes=5)
    token_record = SimpleNamespace(
        consumed_at=None,
        expires_at=future,
        user=None,
        user_id=uuid.uuid4(),
    )

    monkeypatch.setattr(
        auth_api,
        "get_reset_token",
        lambda _db, token: token_record,
    )

    resp = await _post_password_reset(
        {
            "token": "missing-user-token",
            "password": "MissingUserPass1!",
            "confirmPassword": "MissingUserPass1!",
        }
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    assert body["status"] == "invalid"
    assert "Request a new password reset email" in body["detail"]


async def test_password_reset_request_respects_user_cooldown(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    monkeypatch.setattr("app.utils.password_reset.PASSWORD_RESET_REQUEST_COOLDOWN", 60)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    with SessionLocal() as db:
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user_id)
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.PASSWORD_RESET)
            .all()
        )
        assert len(tokens) == 1


async def test_password_reset_request_respects_daily_limit(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    monkeypatch.setattr("app.utils.password_reset.PASSWORD_RESET_DAILY_LIMIT", 2)
    monkeypatch.setattr("app.utils.password_reset.PASSWORD_RESET_REQUEST_COOLDOWN", 0)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    for _ in range(3):
        resp = await _post_password_forgot(email=email)
        assert resp.status_code == 202

    assert len(sent_messages) == 2

    with SessionLocal() as db:
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user_id)
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.PASSWORD_RESET)
            .all()
        )
        assert len(tokens) == 2


async def test_password_reset_request_is_case_insensitive(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    mixed_case = email.upper()
    resp = await _post_password_forgot(email=mixed_case)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    token = _parse_token(sent_messages[0].get_content())

    with SessionLocal() as db:
        record = _get_latest_reset_token(db, user_id)
        assert record is not None
        assert record.token_hash == _hash_token(token)


async def test_password_reset_accepts_whitespace_token(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())
    padded_token = f"  {reset_token}\n"

    new_password = "WhitespaceOk1!"
    resp = await _post_password_reset(
        {
            "token": padded_token,
            "password": new_password,
            "confirmPassword": new_password,
        }
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 2

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(new_password, user.password_hash)


async def test_password_reset_ignores_unverified_email(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    unique_email = f"unverified-{uuid.uuid4().hex}@example.com"
    resp = await client.post(
        "/users",
        json={
            "name": "Una Verified",
            "email": unique_email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": "2025-10-01",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    with SessionLocal() as db:
        user = (
            db.query(models.User)
            .filter(models.User.email == unique_email)
            .one()
        )
        user_id = str(user.id)

    resp = await _post_password_forgot(email=unique_email)
    assert resp.status_code == 202
    assert len(sent_messages) == 0

    with SessionLocal() as db:
        user = db.get(models.User, uuid.UUID(user_id))
        assert user is not None
        assert user.email_verified_at is None
        count = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user.id)
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.PASSWORD_RESET)
            .count()
        )
        assert count == 0


async def test_password_reset_password_mismatch_preserves_token(client, monkeypatch):
    sent_messages = _capture_password_reset_email(monkeypatch)

    _token, user_id, register_resp = await register_and_login(return_register_resp=True)
    email = register_resp.json()["email"]

    resp = await _post_password_forgot(email=email)
    assert resp.status_code == 202
    assert len(sent_messages) == 1

    reset_token = _parse_token(sent_messages[0].get_content())

    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": "MismatchOne1!",
            "confirmPassword": "MismatchTwo2!",
        }
    )
    assert resp.status_code == 422
    assert len(sent_messages) == 1

    with SessionLocal() as db:
        record = _get_latest_reset_token(db, user_id)
        assert record is not None
        assert record.consumed_at is None

    new_password = "MatchPass123!"
    resp = await _post_password_reset(
        {
            "token": reset_token,
            "password": new_password,
            "confirmPassword": new_password,
        }
    )
    assert resp.status_code == 202
    assert len(sent_messages) == 2

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        assert user is not None
        assert verify_password(new_password, user.password_hash)
