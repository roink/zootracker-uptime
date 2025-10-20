import re
import uuid
from datetime import UTC, datetime, timedelta

from app import models
from app.auth import create_access_token
from app.database import SessionLocal
from app import rate_limit

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


def test_signup_triggers_verification_email(monkeypatch):
    client.cookies.clear()
    user_info, messages = _register_user(monkeypatch)
    body = messages[0].get_content()
    assert user_info["email"].lower() in body.lower()
    assert "verification" in body.lower()
    assert "verify?uid=" in body
    assert "verify?email=" in body
    assert _parse_token(body)
    assert _parse_code(body)


def test_resend_respects_cooldown(monkeypatch):
    client.cookies.clear()
    user_info, _messages = _register_user(monkeypatch)

    access_token, _ = create_access_token(user_info["id"])

    with SessionLocal() as db:
        token_record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.EMAIL_VERIFICATION)
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert token_record is not None
        token_record.created_at = token_record.created_at - timedelta(minutes=2)
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
    _reset_verify_rate_limits()
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
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user.id)
            .all()
        )
        assert tokens
        assert all(token.consumed_at is not None for token in tokens)


def test_verify_email_with_code(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
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
        tokens = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == user.id)
            .all()
        )
        assert tokens
        assert all(token.consumed_at is not None for token in tokens)


def test_verify_email_generic_failure(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()

    # Unknown user should receive the generic 202 response.
    resp_unknown = client.post(
        "/auth/verify",
        json={"email": "ghost@example.com", "code": "123456"},
    )
    assert resp_unknown.status_code == 202
    detail = resp_unknown.json()["detail"]

    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    # Use a clearly wrong token to force a mismatch while ensuring the same response payload.
    resp_wrong = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": f"{token}extra"},
    )
    assert resp_wrong.status_code == 202
    assert resp_wrong.json()["detail"] == detail


def test_resend_invalidates_previous_token(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
    user_info, messages = _register_user(monkeypatch)
    first_token = _parse_token(messages[0].get_content())
    messages.clear()

    with SessionLocal() as db:
        token_record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert token_record is not None
        token_record.created_at = token_record.created_at - timedelta(minutes=2)
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


def test_verification_token_cannot_be_reused(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
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


def test_expired_token_is_rejected(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

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

    resp = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert resp.status_code == 202

    with SessionLocal() as db:
        user = db.get(models.User, user_info["id"])
        assert user.email_verified_at is None


def test_verify_email_rate_limit(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
    user_info, _messages = _register_user(monkeypatch)

    payload = {"email": user_info["email"], "code": "000000"}
    # Exhaust the allowed attempts with invalid codes.
    for _ in range(5):
        resp = client.post("/auth/verify", json=payload)
        assert resp.status_code == 202

    resp_blocked = client.post("/auth/verify", json=payload)
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too Many Requests"


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


def test_anonymous_resend_generic_response(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
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


    monkeypatch.setattr("app.utils.email_verification.send_email_via_smtp", _capture)
    monkeypatch.setattr("app.utils.email_sender.send_email_via_smtp", _capture)

def test_anonymous_resend_sends_email_for_unverified_user(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
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
        token_record = (
            db.query(models.VerificationToken)
            .filter(models.VerificationToken.user_id == uuid.UUID(user_info["id"]))
            .filter(models.VerificationToken.kind == models.VerificationTokenKind.EMAIL_VERIFICATION)
            .order_by(models.VerificationToken.created_at.desc())
            .first()
        )
        assert token_record is not None
        token_record.created_at = token_record.created_at - timedelta(minutes=2)
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
    _reset_verify_rate_limits()

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
    _reset_verify_rate_limits()
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


def test_verification_revokes_active_sessions(monkeypatch):
    client.cookies.clear()
    _reset_verify_rate_limits()
    user_info, messages = _register_user(monkeypatch)
    token = _parse_token(messages[0].get_content())

    with SessionLocal() as db:
        user = db.get(models.User, user_info["id"])
        assert user is not None
        now = datetime.now(UTC)
        for idx in range(2):
            refresh = models.RefreshToken(
                user_id=user.id,
                token_hash=f"token-hash-{idx}-{uuid.uuid4()}",
                family_id=uuid.uuid4(),
                issued_at=now - timedelta(minutes=5),
                expires_at=now + timedelta(days=1),
                last_used_at=now - timedelta(minutes=1),
            )
            db.add(refresh)
        db.commit()

    verify_resp = client.post(
        "/auth/verify",
        json={"uid": user_info["id"], "token": token},
    )
    assert verify_resp.status_code == 200

    with SessionLocal() as db:
        records = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.user_id == uuid.UUID(user_info["id"]))
            .all()
        )
        assert records
        for record in records:
            assert record.revoked_at is not None
            assert record.revocation_reason == "email_verified"


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
