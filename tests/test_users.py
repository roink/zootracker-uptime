from app import models
from app.database import SessionLocal

from .conftest import (
    CONSENT_VERSION,
    client,
    register_and_login,
    TEST_PASSWORD,
    mark_user_verified,
)

_counter = 0  # used to generate unique email addresses
_GENERIC_SIGNUP_DETAIL = "If the address can be used, we'll send instructions via email."

def test_create_user_and_authenticate():
    """Ensure that a new user can register and obtain a token."""
    token, _ = register_and_login()
    assert token

def test_create_user_empty_fields():
    """Empty strings for required user fields should fail."""
    resp = client.post(
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

def test_create_user_extra_field_rejected():
    """Unknown fields should result in a 422 error."""
    resp = client.post(
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

def test_create_user_name_too_long():
    long_name = "a" * 256
    resp = client.post(
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

def test_create_user_email_too_long():
    # construct an email longer than 255 characters
    local_part = "a" * 244
    long_email = f"{local_part}@example.com"
    resp = client.post(
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

def test_create_user_password_too_long():
    long_pw = "p" * 256
    resp = client.post(
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

def test_create_user_password_too_short():
    """Passwords shorter than 8 characters should be rejected."""
    resp = client.post(
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


def test_create_user_requires_data_protection_consent():
    """Registrations must include consent to the data protection statement."""
    resp = client.post(
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


def test_consent_validation_error_points_to_field():
    """Consent validation errors should reference the consent field path."""
    resp = client.post(
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

def test_create_user_requires_json():
    global _counter
    email = f"json{_counter}@example.com"
    _counter += 1
    resp = client.post(
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

def test_create_user_accepts_charset():
    """Content type with charset parameter should be accepted."""
    global _counter
    email = f"jsoncharset{_counter}@example.com"
    _counter += 1
    resp = client.post(
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
    assert body == {"detail": _GENERIC_SIGNUP_DETAIL}

def test_create_user_response_fields():
    """Registration response should not expose account details."""
    global _counter
    email = f"fields{_counter}@example.com"
    _counter += 1
    resp = client.post(
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
    assert body == {"detail": _GENERIC_SIGNUP_DETAIL}

def test_login_empty_username_password():
    """Login with empty credentials should return 400."""
    resp = client.post(
        "/auth/login",
        data={"username": "", "password": ""},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400

def test_login_endpoint():
    global _counter
    email = f"alias{_counter}@example.com"
    _counter += 1
    resp = client.post(
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
        mark_user_verified(user.id)
    resp = client.post(
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

def test_login_response_excludes_password_fields():
    """Login endpoint should not leak password details."""
    global _counter
    email = f"token{_counter}@example.com"
    _counter += 1
    resp = client.post(
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
        mark_user_verified(user.id)
    resp = client.post(
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


def test_no_user_listing_endpoint():
    """Ensure there is no GET /users endpoint."""
    resp = client.get("/users")
    assert resp.status_code in {404, 405}


def test_register_response_sanitized():
    """Ensure registration responses remain generic."""
    _token, _user_id, resp = register_and_login(return_register_resp=True)

    data = resp.json()

    assert data == {"detail": _GENERIC_SIGNUP_DETAIL}


def test_registration_persists_privacy_consent_metadata():
    """Registration should persist consent metadata for compliance audits."""
    global _counter
    email = f"consentmeta{_counter}@example.com"
    _counter += 1
    resp = client.post(
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


def test_register_rejects_email_with_different_case():
    """Email uniqueness should be case-insensitive."""
    global _counter
    email = f"case{_counter}@example.com"
    _counter += 1
    first = client.post(
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
    assert first.json() == {"detail": _GENERIC_SIGNUP_DETAIL}
    duplicate = client.post(
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
    assert duplicate.json() == {"detail": _GENERIC_SIGNUP_DETAIL}

    with SessionLocal() as db:
        count = db.query(models.User).filter(models.User.email == email).count()
        assert count == 1

