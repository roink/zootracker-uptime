from app import models
from app.api.users import GENERIC_SIGNUP_MESSAGE
from app.database import SessionLocal

from .conftest import (
    CONSENT_VERSION,
    register_and_login,
    TEST_PASSWORD,
    mark_user_verified,
)

_counter = 0  # used to generate unique email addresses

async def test_create_user_and_authenticate(client):
    """Ensure that a new user can register and obtain a token."""
    token, _ = await register_and_login()
    assert token

async def test_create_user_empty_fields(client):
    """Empty strings for required user fields should fail."""
    resp = await client.post(
        "/users",
        json={
            "name": "",
            "email": "",
            "password": "",
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422

async def test_create_user_extra_field_rejected(client):
    """Unknown fields should result in a 422 error."""
    resp = await client.post(
        "/users",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
            "unexpected": "boom",
        },
    )
    assert resp.status_code == 422

async def test_create_user_name_too_long(client):
    long_name = "a" * 256
    resp = await client.post(
        "/users",
        json={
            "name": long_name,
            "email": "toolong@example.com",
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422

async def test_create_user_email_too_long(client):
    # construct an email longer than 255 characters
    local_part = "a" * 244
    long_email = f"{local_part}@example.com"
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": long_email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422

async def test_create_user_password_too_long(client):
    long_pw = "p" * 256
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": long_pw,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422

async def test_create_user_password_too_short(client):
    """Passwords shorter than 8 characters should be rejected."""
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": "shortpw@example.com",
            "password": "short",
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422


async def test_create_user_requires_data_protection_consent(client):
    """Registrations must include consent to the data protection statement."""
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": "privacy@example.com",
            "password": TEST_PASSWORD,
            "accepted_data_protection": False,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422


async def test_consent_validation_error_points_to_field(client):
    """Consent validation errors should reference the consent field path."""
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": "privacy-loc@example.com",
            "password": TEST_PASSWORD,
            "accepted_data_protection": False,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any(
        error.get("loc") == ["body", "accepted_data_protection"] for error in detail
    )

async def test_create_user_requires_json(client):
    global _counter
    email = f"json{_counter}@example.com"
    _counter += 1
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415

async def test_create_user_accepts_charset(client):
    """Content type with charset parameter should be accepted."""
    global _counter
    email = f"jsoncharset{_counter}@example.com"
    _counter += 1
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
        headers={"content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body == {"detail": GENERIC_SIGNUP_MESSAGE}

async def test_create_user_response_fields(client):
    """Registration response should not expose account details."""
    global _counter
    email = f"fields{_counter}@example.com"
    _counter += 1
    resp = await client.post(
        "/users",
        json={
            "name": "Alice",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body == {"detail": GENERIC_SIGNUP_MESSAGE}

async def test_login_empty_username_password(client):
    """Login with empty credentials should return 400."""
    resp = await client.post(
        "/auth/login",
        data={"username": "", "password": ""},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400

async def test_login_endpoint(client):
    global _counter
    email = f"alias{_counter}@example.com"
    _counter += 1
    resp = await client.post(
        "/users",
        json={
            "name": "Alias",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 202
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.email == email).one()
        await mark_user_verified(user.id)
    resp = await client.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "expires_in" in data
    assert "user_id" in data
    # ensure password hashes are not returned
    assert "password_hash" not in data
    assert "password_salt" not in data

async def test_login_response_excludes_password_fields(client):
    """Login endpoint should not leak password details."""
    global _counter
    email = f"token{_counter}@example.com"
    _counter += 1
    resp = await client.post(
        "/users",
        json={
            "name": "Token",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 202
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.email == email).one()
        await mark_user_verified(user.id)
    resp = await client.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data
    assert "expires_in" in data
    assert "password_hash" not in data
    assert "password_salt" not in data


async def test_no_user_listing_endpoint(client):
    """Ensure there is no GET /users endpoint."""
    resp = await client.get("/users")
    assert resp.status_code in {404, 405}


async def test_register_response_sanitized(client):
    """Ensure registration responses remain generic."""
    _token, _user_id, resp = await register_and_login(return_register_resp=True)

    data = resp.json()

    assert data == {"detail": GENERIC_SIGNUP_MESSAGE}


async def test_registration_persists_privacy_consent_metadata(client):
    """Registration should persist consent metadata for compliance audits."""
    global _counter
    email = f"consentmeta{_counter}@example.com"
    _counter += 1
    resp = await client.post(
        "/users",
        json={
            "name": "Consent",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 202

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).one()
        assert user.privacy_consent_version == CONSENT_VERSION
        assert user.privacy_consent_at is not None
        assert user.privacy_consent_at.tzinfo is not None
        assert user.privacy_consent_ip is not None
        assert user.privacy_consent_ip != ""
    finally:
        db.close()


async def test_register_rejects_email_with_different_case(client):
    """Email uniqueness should be case-insensitive."""
    global _counter
    email = f"case{_counter}@example.com"
    _counter += 1
    first = await client.post(
        "/users",
        json={
            "name": "Case",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert first.status_code == 202
    assert first.json() == {"detail": GENERIC_SIGNUP_MESSAGE}
    duplicate = await client.post(
        "/users",
        json={
            "name": "Case",
            "email": email.upper(),
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert duplicate.status_code == 202
    assert duplicate.json() == {"detail": GENERIC_SIGNUP_MESSAGE}

    with SessionLocal() as db:
        count = db.query(models.User).filter(models.User.email == email).count()
        assert count == 1

