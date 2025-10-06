from datetime import datetime, timedelta, UTC

from app import models
from app.config import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    REFRESH_IDLE_TTL,
)
from app.database import SessionLocal

from httpx import Cookies

from .conftest import client, register_and_login


def _login_and_get_response(email: str, password: str):
    client.cookies.clear()
    register = client.post(
        "/users",
        json={"name": "Auth", "email": email, "password": password},
    )
    assert register.status_code == 200
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response


def test_login_sets_secure_cookies_and_headers():
    email = "cookie@example.com"
    response = _login_and_get_response(email, "supersecret")
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


def _perform_refresh(csrf_token: str | None = None, refresh_token: str | None = None):
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
    return client.post("/auth/refresh", headers=headers, cookies=cookies)


def test_refresh_rotates_tokens_and_sets_cache_headers():
    token, _ = register_and_login()
    assert token
    original_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    original_csrf = client.cookies.get(CSRF_COOKIE_NAME)

    resp = client.post(
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
    reuse = _perform_refresh(original_csrf, original_refresh)
    assert reuse.status_code == 401
    failure = client.post("/auth/refresh", headers={CSRF_HEADER_NAME: rotated_csrf})
    assert failure.status_code == 401


def test_refresh_requires_csrf_header():
    register_and_login()
    response = client.post("/auth/refresh")
    assert response.status_code == 403


def test_refresh_enforces_idle_timeout():
    register_and_login()
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    db = SessionLocal()
    try:
        token = db.query(models.RefreshToken).order_by(models.RefreshToken.issued_at.desc()).first()
        token.last_used_at = datetime.now(UTC) - timedelta(seconds=REFRESH_IDLE_TTL + 5)
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_value},
    )
    assert response.status_code == 401


def test_refresh_enforces_absolute_timeout():
    register_and_login()
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    db = SessionLocal()
    try:
        token = db.query(models.RefreshToken).order_by(models.RefreshToken.issued_at.desc()).first()
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/auth/refresh",
        headers={CSRF_HEADER_NAME: csrf_value},
    )
    assert response.status_code == 401


def test_logout_revokes_tokens_and_clears_cookies():
    register_and_login()
    refresh_value = client.cookies.get(REFRESH_COOKIE_NAME)
    csrf_value = client.cookies.get(CSRF_COOKIE_NAME)
    assert refresh_value and csrf_value
    resp = client.post("/auth/logout")
    assert resp.status_code == 204
    assert client.cookies.get(REFRESH_COOKIE_NAME) is None
    assert client.cookies.get(CSRF_COOKIE_NAME) is None
    failure = _perform_refresh(csrf_value, refresh_value)
    client.cookies.clear()
    assert failure.status_code == 401


def test_cors_preflight_allows_credentials():
    response = client.options(
        "/auth/login",
        headers={
            "origin": "http://allowed.example",
            "access-control-request-method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
