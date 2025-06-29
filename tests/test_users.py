import uuid
from datetime import date, datetime
from .conftest import client, register_and_login, SessionLocal

_counter = 0  # used to generate unique email addresses
from app import models

def test_create_user_and_authenticate():
    """Ensure that a new user can register and obtain a token."""
    token, _ = register_and_login()
    assert token

def test_create_user_empty_fields():
    """Empty strings for required user fields should fail."""
    resp = client.post(
        "/users",
        json={"name": "", "email": "", "password": ""},
    )
    assert resp.status_code == 422

def test_create_user_extra_field_rejected():
    """Unknown fields should result in a 422 error."""
    resp = client.post(
        "/users",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "secret",
            "unexpected": "boom",
        },
    )
    assert resp.status_code == 422

def test_create_user_name_too_long():
    long_name = "a" * 256
    resp = client.post(
        "/users",
        json={"name": long_name, "email": "toolong@example.com", "password": "secret"},
    )
    assert resp.status_code == 422

def test_create_user_email_too_long():
    # construct an email longer than 255 characters
    local_part = "a" * 244
    long_email = f"{local_part}@example.com"
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": long_email, "password": "secret"},
    )
    assert resp.status_code == 422

def test_create_user_password_too_long():
    long_pw = "p" * 256
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": "alice@example.com", "password": long_pw},
    )
    assert resp.status_code == 422

def test_create_user_requires_json():
    global _counter
    email = f"json{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": email, "password": "secret"},
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
        json={"name": "Alice", "email": email, "password": "secret"},
        headers={"content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200

def test_login_empty_username_password():
    """Login with empty credentials should return 400."""
    resp = client.post(
        "/token",
        data={"username": "", "password": ""},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400

def test_login_alias_route():
    global _counter
    email = f"alias{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alias", "email": email, "password": "secret"},
    )
    assert resp.status_code == 200
    resp = client.post(
        "/auth/login",
        data={"username": email, "password": "secret"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()

