"""Authentication helpers for password verification and token handling."""

from __future__ import annotations

import base64
import inspect
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.handlers.bcrypt import _BcryptBackend
import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import models
from .config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACCESS_TOKEN_LEEWAY,
    ACCESS_TOKEN_TTL,
    JWT_ALGORITHM,
    JWT_KID,
    JWT_SIGNING_KEY,
    JWT_VERIFYING_KEY,
    REFRESH_ABS_TTL,
    REFRESH_IDLE_TTL,
    TOKEN_PEPPER,
)
from .database import get_db
from .middleware.logging import set_user_context

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = SimpleNamespace(__version__=bcrypt.__version__)

# Skip passlib's bcrypt backend self-tests that assume passwords >72 bytes
# silently truncate instead of raising ValueError under bcrypt>=5.
_BcryptBackend._workrounds_initialized = True

pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    description=f"Access token expires in approximately {ACCESS_TOKEN_EXPIRE_MINUTES} minutes",
)

optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    description="Optional authentication for endpoints that personalize responses",
    auto_error=False,
)

_PEPPER = TOKEN_PEPPER.encode("utf-8")
_DECODE_SUPPORTS_LEEWAY = "leeway" in inspect.signature(jwt.decode).parameters
_ACTIVE_UPDATE_INTERVAL = timedelta(minutes=10)


def _now() -> datetime:
    return datetime.now(UTC)


def _maybe_touch_last_active(
    db: Session, user: models.User, *, current_time: datetime | None = None
) -> None:
    """Update ``last_active_at`` when the stored value is stale."""

    now = current_time or _now()
    cutoff = now - _ACTIVE_UPDATE_INTERVAL
    stmt = (
        sa.update(models.User)
        .where(models.User.id == user.id)
        .where(
            sa.or_(
                models.User.last_active_at.is_(None),
                models.User.last_active_at <= cutoff,
            )
        )
        .values(last_active_at=now)
    )
    result = db.execute(stmt)
    if result.rowcount:
        db.commit()
        user.last_active_at = now


def hash_password(password: str) -> str:
    """Return a hashed password for storage using bcrypt with SHA-256 pre-hashing."""

    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against the stored hash using bcrypt with SHA-256 pre-hashing."""

    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def create_access_token(
    subject: str,
    *,
    scope: str | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    """Generate a signed JWT token for authentication and return it with its expiry."""

    issued_at = _now()
    lifetime = expires_delta or timedelta(seconds=ACCESS_TOKEN_TTL)
    expire = issued_at + lifetime
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if scope:
        payload["scope"] = scope
    headers: dict[str, Any] = {}
    if JWT_KID:
        headers["kid"] = JWT_KID
    token = jwt.encode(
        payload,
        JWT_SIGNING_KEY,
        algorithm=JWT_ALGORITHM,
        headers=headers or None,
    )
    return token, expire


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode a JWT using the configured verification key."""

    options: dict[str, Any] = {"verify_aud": False}
    if ACCESS_TOKEN_LEEWAY and not _DECODE_SUPPORTS_LEEWAY:
        options["leeway"] = ACCESS_TOKEN_LEEWAY
    kwargs: dict[str, Any] = {"options": options}
    if ACCESS_TOKEN_LEEWAY and _DECODE_SUPPORTS_LEEWAY:
        kwargs["leeway"] = ACCESS_TOKEN_LEEWAY
    decoded = jwt.decode(
        token,
        JWT_VERIFYING_KEY,
        algorithms=[JWT_ALGORITHM],
        **kwargs,
    )
    return cast(dict[str, Any], decoded)


def get_user(db: Session, email: str) -> models.User | None:
    """Retrieve a user by email or return ``None`` if not found."""

    normalized = email.strip()
    if not normalized:
        return None
    lowered = normalized.lower()
    result = (
        db.query(models.User)
        .filter(sa.func.lower(models.User.email) == lowered)
        .first()
    )
    return cast(models.User | None, result)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Return the authenticated user based on the provided JWT token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        uuid_val = uuid.UUID(str(user_id))
    except ValueError:
        raise credentials_exception

    user = cast(models.User | None, db.get(models.User, uuid_val))
    if user is None:
        raise credentials_exception
    set_user_context(str(user.id))
    _maybe_touch_last_active(db, user)
    return user


def get_optional_user(
    token: str | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Return the authenticated user when a bearer token is supplied."""

    if not token:
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        uuid_val = uuid.UUID(str(user_id))
    except ValueError:
        raise credentials_exception

    user = cast(models.User | None, db.get(models.User, uuid_val))
    if user is None:
        raise credentials_exception
    set_user_context(str(user.id))
    _maybe_touch_last_active(db, user)
    return user


def generate_refresh_token() -> str:
    """Generate an opaque refresh token string."""

    return base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")


def hash_refresh_token(raw_token: str) -> str:
    """Return a SHA-256 hash of the refresh token using the configured pepper."""

    digest = hashlib.sha256(_PEPPER + raw_token.encode("utf-8")).hexdigest()
    return digest


def refresh_token_expired(token: models.RefreshToken, *, now: datetime | None = None) -> bool:
    """Return ``True`` when the refresh token has exceeded idle or absolute limits."""

    current_time = now or _now()
    if token.expires_at <= current_time:
        return True
    if token.last_used_at + timedelta(seconds=REFRESH_IDLE_TTL) <= current_time:
        return True
    return False


def issue_refresh_token(
    db: Session,
    user: models.User,
    *,
    family_id: uuid.UUID | None = None,
    user_agent: str | None = None,
    absolute_expiry: datetime | None = None,
) -> tuple[str, models.RefreshToken]:
    """Persist a new refresh token for the given user and return its plaintext value."""

    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)
    issued_at = _now()
    expires_at = absolute_expiry or issued_at + timedelta(seconds=REFRESH_ABS_TTL)
    record = models.RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        family_id=family_id or uuid.uuid4(),
        issued_at=issued_at,
        expires_at=expires_at,
        last_used_at=issued_at,
        user_agent=user_agent,
    )
    db.add(record)
    db.flush()
    return raw_token, record


def revoke_refresh_family(
    db: Session,
    family_id: uuid.UUID,
    *,
    reason: str | None = None,
    timestamp: datetime | None = None,
) -> None:
    """Mark all refresh tokens in the family as revoked."""

    current_time = timestamp or _now()
    db.query(models.RefreshToken).filter(
        models.RefreshToken.family_id == family_id,
        models.RefreshToken.revoked_at.is_(None),
    ).update(
        {
            models.RefreshToken.revoked_at: current_time,
            models.RefreshToken.revocation_reason: reason,
        },
        synchronize_session=False,
    )

