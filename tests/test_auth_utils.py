from datetime import timedelta

import pytest
from fastapi import HTTPException

import app.auth as auth
import app.config as app_config
from app.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    get_optional_user,
    get_user,
    hash_password,
    verify_password,
)
from app.config import ACCESS_TOKEN_LEEWAY
from app.database import SessionLocal
from .conftest import register_and_login


def test_password_round_trip_short():
    password = "abcdefghij"
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)


def test_password_round_trip_long_80_bytes():
    password = "x" * 80
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("y" * 80, hashed)


def test_create_token_and_get_current_user():
    _, user_id = register_and_login()
    token, _ = create_access_token(user_id)
    db = SessionLocal()
    try:
        user = get_current_user(token=token, db=db)
        assert str(user.id) == user_id
    finally:
        db.close()


def test_get_current_user_expired_token():
    _, user_id = register_and_login()
    token, _ = create_access_token(
        user_id,
        expires_delta=timedelta(seconds=-(ACCESS_TOKEN_LEEWAY + 5)),
    )
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException):
            get_current_user(token=token, db=db)
    finally:
        db.close()


def test_create_access_token_includes_scope_and_kid(monkeypatch):
    monkeypatch.setattr(auth, "JWT_KID", "test-key", raising=False)

    captured = {}

    def fake_encode(payload, key, algorithm, headers=None):
        captured["payload"] = payload
        captured["headers"] = headers
        captured["key"] = key
        captured["algorithm"] = algorithm
        return "encoded-token"

    monkeypatch.setattr(auth.jwt, "encode", fake_encode)

    token, _ = create_access_token("user-123", scope="read")

    assert token == "encoded-token"
    assert captured["headers"]["kid"] == "test-key"
    assert captured["payload"]["scope"] == "read"
    assert captured["payload"]["sub"] == "user-123"


def test_decode_access_token_respects_leeway(monkeypatch):
    monkeypatch.setattr(app_config, "ACCESS_TOKEN_LEEWAY", 30, raising=False)
    monkeypatch.setattr(auth, "ACCESS_TOKEN_LEEWAY", 30, raising=False)
    monkeypatch.setattr(auth, "_DECODE_SUPPORTS_LEEWAY", True, raising=False)

    captured_kwargs = {}

    def fake_decode(token, key, algorithms, **kwargs):
        captured_kwargs.update(kwargs)
        return {"sub": "abc123"}

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    result = decode_access_token("token-value")

    assert result == {"sub": "abc123"}
    assert captured_kwargs["leeway"] == 30
    assert captured_kwargs["options"] == {"verify_aud": False}


def test_decode_access_token_omits_leeway_when_not_supported(monkeypatch):
    monkeypatch.setattr(app_config, "ACCESS_TOKEN_LEEWAY", 15, raising=False)
    monkeypatch.setattr(auth, "ACCESS_TOKEN_LEEWAY", 15, raising=False)
    monkeypatch.setattr(auth, "_DECODE_SUPPORTS_LEEWAY", False, raising=False)

    captured_kwargs = {}

    def fake_decode(token, key, algorithms, **kwargs):
        captured_kwargs.update(kwargs)
        return {"sub": "def456"}

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    result = decode_access_token("token-value")

    assert result == {"sub": "def456"}
    assert "leeway" not in captured_kwargs
    assert captured_kwargs["options"] == {"verify_aud": False, "leeway": 15}


def test_get_user_returns_none_for_whitespace_email():
    db = SessionLocal()
    try:
        assert get_user(db, "   \t\n  ") is None
    finally:
        db.close()


def test_get_current_user_missing_sub_raises(monkeypatch):
    monkeypatch.setattr(auth, "decode_access_token", lambda token: {}, raising=False)
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            get_current_user(token="irrelevant", db=db)
        assert exc.value.status_code == 401
    finally:
        db.close()


def test_get_current_user_invalid_uuid_raises(monkeypatch):
    monkeypatch.setattr(
        auth, "decode_access_token", lambda token: {"sub": "not-a-uuid"}, raising=False
    )
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            get_current_user(token="irrelevant", db=db)
        assert exc.value.status_code == 401
    finally:
        db.close()


def test_get_optional_user_missing_sub_raises(monkeypatch):
    monkeypatch.setattr(auth, "decode_access_token", lambda token: {}, raising=False)
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            get_optional_user(token="optional", db=db)
        assert exc.value.status_code == 401
    finally:
        db.close()


def test_get_optional_user_invalid_uuid_raises(monkeypatch):
    monkeypatch.setattr(
        auth, "decode_access_token", lambda token: {"sub": "bad-uuid"}, raising=False
    )
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc:
            get_optional_user(token="optional", db=db)
        assert exc.value.status_code == 401
    finally:
        db.close()
