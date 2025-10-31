from datetime import UTC, datetime, timedelta

from app import models
from app.config import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    REFRESH_IDLE_TTL,
)
from app.database import SessionLocal

from httpx import Cookies

from .conftest import CONSENT_VERSION, register_and_login, mark_user_verified, get_client


async def _register_user(email: str, password: str, name: str = "Auth") -> models.User:
    client = get_client()
    """Register ``email`` and return the persisted user record."""

    resp = await client.post(
        "/users",
        json={
            "name": name,
            "email": email,
            "password": password,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert resp.status_code == 202
    with SessionLocal() as db:
        return db.query(models.User).filter(models.User.email == email).one()


async def _login_and_get_response(email: str, password: str):
    client = get_client()
    client.cookies.clear()
    user = await _register_user(email, password)
    await mark_user_verified(user.id)
    response = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response


async def test_login_accepts_email_case_variations(client):
    email = "caseflex@example.com"
    password = "supersecret"
    client.cookies.clear()
    user = await _register_user(email, password, name="Case")
    await mark_user_verified(user.id)

    response = await client.post(
        "/auth/login",
        data={"username": email.upper(), "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200


async def test_login_sets_secure_cookies_and_headers(client):
    email = "cookie@example.com"
    response = await _login_and_get_response(email, "supersecret")
    cookies = response.headers.get_list("set-cookie")
    assert any(REFRESH_COOKIE_NAME in cookie for cookie in cookies)
    refresh_cookie = next(cookie for cookie in cookies if REFRESH_COOKIE_NAME in cookie)
    assert "HttpOnly" in refresh_cookie
    assert "Path=/auth" in refresh_cookie
    assert "SameSite=Lax" in refresh_cookie
    csrf_cookie = next(cookie for cookie in cookies if CSRF_COOKIE_NAME in cookie)
    assert "HttpOnly" not in csrf_cookie
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"


async def test_login_updates_activity_timestamps(client):
    email = "activity@example.com"
    password = "supersecret"
    client.cookies.clear()
    user = await _register_user(email, password, name="Active")
    await mark_user_verified(user.id)

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).one()
        assert user.last_login_at is None
        assert user.last_active_at is None
    finally:
        db.close()

    response = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).one()
        assert user.last_login_at is not None
        assert user.last_active_at is not None
        delta = abs((user.last_active_at - user.last_login_at).total_seconds())
        assert delta < 1.5
    finally:
        db.close()


async def _perform_refresh(csrf_token: str | None = None, refresh_token: str | None = None):
    client = get_client()
    headers = {}
    if csrf_token is not None:
        headers[CSRF_HEADER_NAME] = csrf_token
    cookies: Cookies | None = None
    if csrf_token is not None or refresh_token is not None:
        cookies = Cookies()
        if refresh_token is not None:
            cookies.set(REFRESH_COOKIE_NAME, refresh_token, path="/auth")
        if csrf_token is not None:
            cookies.set(CSRF_COOKIE_NAME, csrf_token, path="/")
    return await client.post("/auth/refresh", headers=headers, cookies=cookies)


async def test_refresh_rotates_tokens_and_sets_cache_headers(client):
    token, _ = await register_and_login()
    assert token
    original_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    original_csrf = client.cookies.get(CSRF_COOKIE_NAME)

    resp = await client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: original_csrf},
    )
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["Pragma"] == "no-cache"
    rotated_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    rotated_csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert rotated_refresh != original_refresh
    assert rotated_csrf != original_csrf
    # Attempt reuse of the old token should revoke the family
    reuse = await _perform_refresh(original_csrf, original_refresh)
    assert reuse.status_code == 401
    assert reuse.headers["Cache-Control"] == "no-store"
    assert reuse.headers.get("Pragma") == "no-cache"
    failure = await client.post("/auth/refresh", headers={CSRF_HEADER_NAME: rotated_csrf})
    assert failure.status_code == 401
    assert failure.headers["Cache-Control"] == "no-store"
    assert failure.headers.get("Pragma") == "no-cache"


async def test_refresh_requires_csrf_header(client):
    await register_and_login()
    response = await client.post("/auth/refresh")
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("Pragma") == "no-cache"


async def test_refresh_requires_refresh_cookie_even_with_valid_csrf_pair(client):
    await register_and_login()
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_value is not None

    if REFRESH_COOKIE_NAME in client.cookies:
        del client.cookies[REFRESH_COOKIE_NAME]
    response = await _perform_refresh(csrf_token=csrf_value)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing refresh token"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("Pragma") == "no-cache"


async def test_refresh_rejects_invalid_refresh_cookie(client):
    await register_and_login()
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_value is not None

    if REFRESH_COOKIE_NAME in client.cookies:
        del client.cookies[REFRESH_COOKIE_NAME]
    response = await _perform_refresh(
        csrf_token=csrf_value, refresh_token="tampered-token"
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("Pragma") == "no-cache"


async def test_authenticated_request_refreshes_last_active_when_stale(client):
    token, user_id = await register_and_login()
    db = SessionLocal()
    try:
        user = db.get(models.User, user_id)
        assert user is not None
        assert user.last_active_at is not None
        stale_time = user.last_active_at - timedelta(minutes=30)
        user.last_active_at = stale_time
        db.commit()
    finally:
        db.close()

    response = await client.get(
        "/visits",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        user = db.get(models.User, user_id)
        assert user is not None
        assert user.last_active_at is not None
        assert user.last_active_at > stale_time
        assert datetime.now(UTC) - user.last_active_at < timedelta(minutes=5)
    finally:
        db.close()


async def test_authenticated_request_does_not_touch_last_active_when_recent(client):
    token, user_id = await register_and_login()

    db = SessionLocal()
    try:
        user = db.get(models.User, user_id)
        assert user is not None
        user.last_active_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        user = db.get(models.User, user_id)
        assert user is not None
        recent_active_at = user.last_active_at
    finally:
        db.close()

    response = await client.get(
        "/visits",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        user = db.get(models.User, user_id)
        assert user is not None
        assert user.last_active_at == recent_active_at
    finally:
        db.close()


async def test_refresh_enforces_idle_timeout(client):
    await register_and_login()
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    db = SessionLocal()
    try:
        token = db.query(models.RefreshToken).order_by(models.RefreshToken.issued_at.desc()).first()
        token.last_used_at = datetime.now(UTC) - timedelta(seconds=REFRESH_IDLE_TTL + 5)
        db.commit()
    finally:
        db.close()
    response = await client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_value},
    )
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("Pragma") == "no-cache"


async def test_refresh_enforces_absolute_timeout(client):
    await register_and_login()
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    db = SessionLocal()
    try:
        token = db.query(models.RefreshToken).order_by(models.RefreshToken.issued_at.desc()).first()
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    response = await client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_value},
    )
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers.get("Pragma") == "no-cache"


async def test_logout_revokes_tokens_and_clears_cookies(client):
    await register_and_login()
    refresh_value = client.cookies.get(REFRESH_COOKIE_NAME)
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    assert refresh_value and csrf_value
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204
    assert client.cookies.get(REFRESH_COOKIE_NAME) is None
    assert client.cookies.get(CSRF_COOKIE_NAME) is None
    failure = await _perform_refresh(csrf_value, refresh_value)
    client.cookies.clear()
    assert failure.status_code == 401
    assert failure.headers["Cache-Control"] == "no-store"
    assert failure.headers.get("Pragma") == "no-cache"


async def test_cors_preflight_allows_credentials(client):
    response = await client.options(
        "/auth/login",
        headers={
            "origin": "http://allowed.example",
            "access-control-request-method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
