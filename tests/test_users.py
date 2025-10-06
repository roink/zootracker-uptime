from .conftest import client, register_and_login, TEST_PASSWORD

_counter = 0  # used to generate unique email addresses

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
            "password": TEST_PASSWORD,
            "unexpected": "boom",
        },
    )
    assert resp.status_code == 422

def test_create_user_name_too_long():
    long_name = "a" * 256
    resp = client.post(
        "/users",
        json={"name": long_name, "email": "toolong@example.com", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 422

def test_create_user_email_too_long():
    # construct an email longer than 255 characters
    local_part = "a" * 244
    long_email = f"{local_part}@example.com"
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": long_email, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 422

def test_create_user_password_too_long():
    long_pw = "p" * 256
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": "alice@example.com", "password": long_pw},
    )
    assert resp.status_code == 422

def test_create_user_password_too_short():
    """Passwords shorter than 8 characters should be rejected."""
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": "shortpw@example.com", "password": "short"},
    )
    assert resp.status_code == 422

def test_create_user_requires_json():
    global _counter
    email = f"json{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": email, "password": TEST_PASSWORD},
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
        json={"name": "Alice", "email": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200
    # response should only include id, name and email
    assert set(resp.json().keys()) == {"id", "name", "email"}

def test_create_user_response_fields():
    """Successful user creation returns only id, name and email."""
    global _counter
    email = f"fields{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": email, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"id", "name", "email"}

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
        json={"name": "Alias", "email": email, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
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
        json={"name": "Token", "email": email, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
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
    """Ensure password fields are not returned in registration responses."""
    token, user_id, resp = register_and_login(return_register_resp=True)

    data = resp.json()

    # Sensitive fields should not be included
    assert "password" not in data
    assert "password_hash" not in data
    assert "password_salt" not in data

    # Only expected fields are present
    assert set(data.keys()) == {"id", "name", "email"}

