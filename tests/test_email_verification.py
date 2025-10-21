import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app import models, rate_limit
from app.auth import create_access_token, issue_refresh_token
from app.config import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    EMAIL_VERIFICATION_DAILY_LIMIT,
    EMAIL_VERIFICATION_RESEND_COOLDOWN,
    REFRESH_COOKIE_NAME,
)
from app.database import SessionLocal
from app.utils.email_verification import code_matches, token_matches

from .conftest import CONSENT_VERSION, TEST_PASSWORD, client, mark_user_verified

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
    assert resp.status_code == 202
    assert sent_messages, "Expected verification email to be sent"
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.email == addr).one()
        user_info = {"id": str(user.id), "name": user.name, "email": user.email}
    return user_info, sent_messages


def _reset_verify_rate_limits():
    """Clear verification rate limiter state between tests."""

    rate_limit.verify_ip_limiter.history.clear()
    rate_limit.verify_identifier_limiter.history.clear()
    rate_limit.verify_failed_ip_limiter.history.clear()
    rate_limit.verify_failed_identifier_limiter.history.clear()
    rate_limit.verify_resend_ip_limiter.history.clear()
    rate_limit.verify_resend_identifier_limiter.history.clear()


def _parse_token(body: str) -> str:
    match = TOKEN_RE.search(body)
    assert match, "Expected token in email body"
    return match.group(1)


def _parse_code(body: str) -> str:
    match = CODE_RE.search(body)
    assert match, "Expected numeric code in email body"
    return match.group(1)


def _generic_detail() -> str:
    return "If the account exists, the verification state was updated."


def _get_user(user_id: str) -> models.User | None:
    with SessionLocal() as db:
        return db.get(models.User, uuid.UUID(str(user_id)))


def _latest_token_record(user_id: str) -> models.VerificationToken | None:
    with SessionLocal() as db:
        return (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(str(user_id)))
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.EMAIL_VERIFICATION)
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )


def _all_tokens(user_id: str) -> list[models.VerificationToken]:
    with SessionLocal() as db:
        return (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(str(user_id)))
            .order_by(models.VerificationToken.created_at.asc())
            .all()
        )


@pytest.fixture(autouse=True)
def _reset_limiters():
    _reset_verify_rate_limits()
    yield
    _reset_verify_rate_limits()


def test_signup_triggers_verification_email(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    body = messages[0].get_content()
    token = _parse_token(body)
    code = _parse_code(body)
    assert user_info["email"].lower() in body.lower()
    assert "verification" in body.lower()
    assert f"verify?uid={user_info['id']}" in body
    assert "verify?email=" in body

    record = _latest_token_record(user_info["id"])
    assert record is not None
    assert token_matches(record, token)
    assert code_matches(record, code)


def test_signup_initial_verification_state(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    body = messages[0].get_content()
    token = _parse_token(body)
    code = _parse_code(body)

    user = _get_user(user_info["id"])
    assert user is not None
    assert user.email_verified_at is None

    record = _latest_token_record(user_info["id"])
    assert record is not None
    assert record.consumed_at is None
    assert record.token_hash
    assert record.code_hash
    assert record.expires_at > datetime.now(UTC)
    assert record.created_at <= datetime.now(UTC)
    assert token_matches(record, token)
    assert code_matches(record, code)


def test_resend_respects_cooldown(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)

    access_token, _ = create_access_token(user_info["id"])

    with SessionLocal() as db:
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert record is not None
        record.created_at = record.created_at - timedelta(minutes=2)
        db.commit()

    resp = client.post(
        "/auth/verification/resend",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"] == "We sent you a new verification email."

    resp = client.post(
        "/auth/verification/resend",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 429
    assert (
        resp.json()["detail"]
        == "We recently sent a verification email. Please check your inbox."
    )


def test_resend_updates_verification_state(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    access_token, _ = create_access_token(user_info["id"])

    with SessionLocal() as db:
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert record is not None
        previous_id = record.id
        previous_hash = record.token_hash
        previous_code_hash = record.code_hash
        record.created_at = record.created_at - timedelta(
            seconds=EMAIL_VERIFICATION_RESEND_COOLDOWN + 10
        )
        db.commit()

    messages.clear()
    resp = client.post(
        "/auth/verification/resend",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"] == "We sent you a new verification email."
    assert len(messages) == 1

    new_body = messages[0].get_content()
    new_token = _parse_token(new_body)
    new_code = _parse_code(new_body)

    new_record = _latest_token_record(user_info["id"])
    assert new_record is not None
    assert new_record.id != previous_id
    assert new_record.token_hash != previous_hash
    assert new_record.code_hash != previous_code_hash
    assert new_record.created_at > datetime.now(UTC) - timedelta(minutes=5)
    assert new_record.consumed_at is None
    assert token_matches(new_record, new_token)
    assert code_matches(new_record, new_code)

    with SessionLocal() as db:
        previous = db.get(models.VerificationToken, previous_id)
        assert previous is not None
        assert previous.consumed_at is not None


def test_resend_enforces_daily_limit(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    access_token, _ = create_access_token(user_info["id"])

    messages.clear()
    for attempt in range(EMAIL_VERIFICATION_DAILY_LIMIT):
        with SessionLocal() as db:
            record = (
                db.query(models.VerificationToken)
                .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
                .order_by(models.VerificationToken.created_at.desc())
                .first()
            )
            assert record is not None
            record.created_at = record.created_at - timedelta(
                seconds=EMAIL_VERIFICATION_RESEND_COOLDOWN + 1
            )
            db.commit()

        resp = client.post(
            "/auth/verification/resend",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if attempt < EMAIL_VERIFICATION_DAILY_LIMIT - 1:
            assert resp.status_code == 202
            assert resp.json()["detail"] == "We sent you a new verification email."
        else:
            assert resp.status_code == 429
            assert (
                resp.json()["detail"]
                == "Daily verification email limit reached. Try again tomorrow."
            )

    assert len(messages) == EMAIL_VERIFICATION_DAILY_LIMIT - 1


@pytest.mark.parametrize("method", ["token", "code"], ids=["token", "code"])
def test_verify_email_succeeds(monkeypatch, method):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    body = messages[0].get_content()
    token = _parse_token(body)
    code = _parse_code(body)

    before = datetime.now(UTC)
    if method == "token":
        payload = {"uid": user_info["id"], "token": token}
    else:
        payload = {"email": user_info["email"], "code": code}

    resp = client.post("/auth/verify", json=payload)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Email verified."

    user = _get_user(user_info["id"])
    assert user is not None
    assert user.email_verified_at is not None
    assert user.email_verified_at >= before
    assert datetime.now(UTC) - user.email_verified_at < timedelta(seconds=5)

    tokens = _all_tokens(user_info["id"])
    assert tokens
    assert all(token.consumed_at is not None for token in tokens)

    assert not rate_limit.verify_failed_ip_limiter.history
    assert not rate_limit.verify_failed_identifier_limiter.history


def test_verify_email_generic_failure(monkeypatch):
    client.cookies.clear()

    resp_unknown = client.post(
        "/auth/verify",
        json={"email": "ghost@example.com", "code": "123456"},
    )
    assert resp_unknown.status_code == 202
    detail = resp_unknown.json()["detail"]

    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())
    code = _parse_code(messages[0].get_content())

    resp_wrong = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": f"{token}extra"},
    )
    assert resp_wrong.status_code == 202
    assert resp_wrong.json()["detail"] == detail

    wrong_code = "0" * len(code)
    if wrong_code == code:
        wrong_code = "1" + "0" * (len(code) - 1)

    resp_wrong_code = client.post(
        "/auth/verify",
        json={"email": user_info["email"], "code": wrong_code},
    )
    assert resp_wrong_code.status_code == 202
    assert resp_wrong_code.json()["detail"] == detail


@pytest.mark.parametrize("method", ["token", "code"], ids=["token", "code"])
def test_verification_rejects_expired_secret(monkeypatch, method):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    body = messages[0].get_content()
    token = _parse_token(body)
    code = _parse_code(body)

    with SessionLocal() as db:
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert record is not None
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    if method == "token":
        payload = {"uid": user_info["id"], "token": token}
    else:
        payload = {"email": user_info["email"], "code": code}

    resp = client.post("/auth/verify", json=payload)
    assert resp.status_code == 202
    assert resp.json()["detail"] == _generic_detail()

    user = _get_user(user_info["id"])
    assert user is not None
    assert user.email_verified_at is None


@pytest.mark.parametrize("method", ["token", "code"], ids=["token", "code"])
def test_cross_user_verification_secret_is_rejected(monkeypatch, method):
    client.cookies.clear()

    user_a, messages_a = _register_user(monkeypatch)
    body_a = messages_a[0].get_content()
    token_a = _parse_token(body_a)
    code_a = _parse_code(body_a)

    user_b, _messages_b = _register_user(monkeypatch)

    if method == "token":
        payload = {"uid": user_b["id"], "token": token_a}
    else:
        payload = {"email": user_b["email"], "code": code_a}

    resp = client.post("/auth/verify", json=payload)
    assert resp.status_code == 202
    assert resp.json()["detail"] == _generic_detail()


def test_verification_token_cannot_be_reused(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    first = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert first.status_code == 200

    second = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert second.status_code == 202
    assert second.json()["detail"] == _generic_detail()


def test_verify_nonexistent_uid_generic_response(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    resp = client.post(
        "/auth/verify",
        json={"uid": str(uuid.uuid4()), "token": token},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"] == _generic_detail()


def test_verify_email_with_malformed_uid(monkeypatch):
    client.cookies.clear()
    _register_user(monkeypatch)

    resp = client.post(
        "/auth/verify",
        json={"uid": "not-a-uuid", "token": "any-token"},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"] == _generic_detail()


def test_post_verification_login_and_refresh(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    verify_resp = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert verify_resp.status_code == 200

    login_resp = client.post(
        "/auth/login",
        data={"username": user_info["email"], "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_resp.status_code == 200
    login_body = login_resp.json()
    assert login_body["email_verified"] is True

    csrf_cookie = client.cookies.get(CSRF_COOKIE_NAME)
    refresh_resp = client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_cookie},
    )
    assert refresh_resp.status_code == 200
    refresh_body = refresh_resp.json()
    assert refresh_body["email_verified"] is True


def test_verify_email_rate_limit_per_identifier(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)

    ip_counter = 0

    def rotating_ip(request):
        nonlocal ip_counter
        ip_counter += 1
        return f"198.51.100.{ip_counter}"

    monkeypatch.setattr("app.rate_limit.get_client_ip", rotating_ip)

    payload = {"email": user_info["email"], "code": "000000"}
    for _ in range(rate_limit.VERIFY_ATTEMPT_LIMIT):
        resp = client.post("/auth/verify", json=payload)
        assert resp.status_code == 202

    resp_blocked = client.post("/auth/verify", json=payload)
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too Many Requests"


def test_verify_email_rate_limit_per_ip(monkeypatch):
    client.cookies.clear()
    _register_user(monkeypatch)

    identifier = "ip-limit@example.com"
    for _ in range(rate_limit.VERIFY_ATTEMPT_LIMIT):
        resp = client.post(
            "/auth/verify",
            json={"email": identifier, "code": "000000"},
        )
        assert resp.status_code == 202

    resp_blocked = client.post(
        "/auth/verify",
        json={"email": identifier, "code": "000000"},
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too Many Requests"


def test_verification_revokes_existing_sessions(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    csrf_nonce = "csrf-session"
    with SessionLocal() as db:
        user = db.get(models.User, uuid.UUID(user_info["id"]))
        assert user is not None
        raw_refresh, _ = issue_refresh_token(db, user, user_agent="pytest")
        db.commit()

    client.cookies.set(REFRESH_COOKIE_NAME, raw_refresh, path="/auth")
    client.cookies.set(CSRF_COOKIE_NAME, csrf_nonce, path="/")

    verify_resp = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert verify_resp.status_code == 200

    refresh_resp = client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_nonce},
    )
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["detail"] == "Refresh token revoked"

    tokens = _all_tokens(user_info["id"])
    assert tokens
    assert all(token.consumed_at is not None for token in tokens)
    assert not rate_limit.verify_failed_ip_limiter.history
    assert not rate_limit.verify_failed_identifier_limiter.history


def test_resend_invalidates_previous_token(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    first_token = _parse_token(messages[0].get_content())
    messages.clear()

    with SessionLocal() as db:
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert record is not None
        record.created_at = record.created_at - timedelta(minutes=2)
        db.commit()

    resp = client.post(
        "/auth/verification/request-resend",
        json={"email": user_info["email"]},
    )
    assert resp.status_code == 202
    assert len(messages) == 1
    second_token = _parse_token(messages[0].get_content())
    assert second_token != first_token

    _reset_verify_rate_limits()
    resp_old = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": first_token},
    )
    assert resp_old.status_code == 202

    resp_new = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": second_token},
    )
    assert resp_new.status_code == 200


def test_resend_denied_when_already_verified(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)
    mark_user_verified(user_info["id"])
    access_token, _ = create_access_token(user_info["id"])

    resp = client.post(
        "/auth/verification/resend",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"] == "Your email address is already verified."


def test_verifying_already_verified_user_is_noop(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())
    mark_user_verified(user_info["id"])

    user = _get_user(user_info["id"])
    assert user is not None
    baseline = user.email_verified_at

    resp = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"] == _generic_detail()

    user = _get_user(user_info["id"])
    assert user is not None
    assert user.email_verified_at == baseline


def test_login_requires_verified_email(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)

    resp = client.post(
        "/auth/login",
        data={"username": user_info["email"], "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 403
    assert "verified" in resp.json()["detail"].lower()


def test_email_case_insensitive_for_verification_and_login(monkeypatch):
    client.cookies.clear()
    mixed_email = "UserCase@example.com"
    user_info, messages = _register_user(monkeypatch, email=mixed_email)
    code = _parse_code(messages[0].get_content())

    pre_login = client.post(
        "/auth/login",
        data={"username": mixed_email.lower(), "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert pre_login.status_code == 403

    verify_resp = client.post(
        "/auth/verify",
        json={"email": mixed_email.upper(), "code": code},
    )
    assert verify_resp.status_code == 200

    post_login = client.post(
        "/auth/login",
        data={"username": mixed_email.swapcase(), "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert post_login.status_code == 200


def test_anonymous_resend_generic_response(monkeypatch):
    client.cookies.clear()
    sent_messages = []

    def _capture(*, settings, message, **kwargs):
        sent_messages.append(message)

    monkeypatch.setattr("app.utils.email_verification.send_email_via_smtp", _capture)
    monkeypatch.setattr("app.utils.email_sender.send_email_via_smtp", _capture)

    resp = client.post(
        "/auth/verification/request-resend",
        json={"email": "ghost@example.com"},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"].startswith("If the account exists")
    assert sent_messages == []


def test_anonymous_resend_sends_email_for_unverified_user(monkeypatch):
    client.cookies.clear()
    sent_messages = []

    def _capture(*, settings, message, **kwargs):
        sent_messages.append(message)

    monkeypatch.setattr("app.utils.email_verification.send_email_via_smtp", _capture)
    monkeypatch.setattr("app.utils.email_sender.send_email_via_smtp", _capture)

    user_info, _messages = _register_user(monkeypatch)
    sent_messages.clear()
    monkeypatch.setattr("app.utils.email_verification.send_email_via_smtp", _capture)
    monkeypatch.setattr("app.utils.email_sender.send_email_via_smtp", _capture)

    with SessionLocal() as db:
        record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert record is not None
        record.created_at = record.created_at - timedelta(minutes=2)
        db.commit()

    resp = client.post(
        "/auth/verification/request-resend",
        json={"email": user_info["email"]},
    )
    assert resp.status_code == 202
    assert resp.json()["detail"].startswith("If the account exists")
    assert sent_messages, "Expected resend email to be queued"


def test_anonymous_resend_rate_limited(monkeypatch):
    client.cookies.clear()

    email = "throttle@example.com"
    for _ in range(rate_limit.VERIFY_RESEND_IP_LIMIT):
        resp = client.post(
            "/auth/verification/request-resend",
            json={"email": email},
        )
        assert resp.status_code == 202

    blocked = client.post(
        "/auth/verification/request-resend",
        json={"email": email},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"].startswith("If the account exists")


def test_anonymous_resend_ignored_for_verified_user(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    original_ids = []

    with SessionLocal() as db:
        user = db.get(models.User, user_info["id"])
        assert user is not None
        now = datetime.now(UTC)
        user.email_verified_at = now
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user.id)
            .all()
        )
        assert tokens
        for token in tokens:
            token.consumed_at = now
            original_ids.append(token.id)
        db.commit()

    messages.clear()
    resp = client.post(
        "/auth/verification/request-resend",
        json={"email": user_info["email"]},
    )
    assert resp.status_code == 202
    assert messages == []

    with SessionLocal() as db:
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .all()
        )
        assert {token.id for token in tokens} == set(original_ids)


def test_user_deletion_cascades_tokens(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)

    with SessionLocal() as db:
        count_before = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .count()
        )
        assert count_before >= 1

        db.query(models.User).filter(models.User.id == uuid.UUID(user_info["id"])).delete()
        db.commit()

        count_after = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .count()
        )
        assert count_after == 0
