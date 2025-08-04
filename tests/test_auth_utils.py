import pytest
from datetime import timedelta
from fastapi import HTTPException

from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.database import SessionLocal
from .conftest import register_and_login


def test_hash_and_verify_round_trip():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_create_token_and_get_current_user():
    _, user_id = register_and_login()
    token = create_access_token({"sub": user_id})
    db = SessionLocal()
    try:
        user = get_current_user(token=token, db=db)
        assert str(user.id) == user_id
    finally:
        db.close()


def test_get_current_user_expired_token():
    _, user_id = register_and_login()
    token = create_access_token({"sub": user_id}, expires_delta=timedelta(seconds=-1))
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException):
            get_current_user(token=token, db=db)
    finally:
        db.close()
