"""Authentication API endpoints."""

from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any, Deque

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..utils.email_verification import (
    can_issue_again,
    clear_verification_state,
    code_matches,
    enqueue_verification_email,
    issue_verification_token,
    token_matches,
)
from ..auth import (
    create_access_token,
    get_current_user,
    get_user,
    hash_refresh_token,
    issue_refresh_token,
    refresh_token_expired,
    revoke_refresh_family,
    verify_password,
)
from ..config import (
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_ABS_TTL,
    REFRESH_COOKIE_NAME,
)
from ..database import get_db
from ..logging import anonymize_ip
from ..middleware.logging import set_user_context
from ..utils.network import get_client_ip

router = APIRouter()


auth_logger = logging.getLogger("app.auth")

_FAILURE_WINDOW_SECONDS = 60
_FAILURE_LOG_LIMIT = 10
_failure_attempts: dict[str, Deque[float]] = defaultdict(deque)


def _should_log_failure(ip_key: str) -> bool:
    now = time.monotonic()
    history = _failure_attempts[ip_key]
    while history and now - history[0] > _FAILURE_WINDOW_SECONDS:
        history.popleft()
    history.append(now)
    return len(history) <= _FAILURE_LOG_LIMIT


def _now() -> datetime:
    return datetime.now(UTC)


def _cache_busting_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


_REFRESH_COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: Response, value: str, max_age: int) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=value,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=max_age,
        path=_REFRESH_COOKIE_PATH,
        domain=COOKIE_DOMAIN,
    )


def _set_csrf_cookie(response: Response, value: str, max_age: int) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=value,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=max_age,
        path="/",
        domain=COOKIE_DOMAIN,
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=_REFRESH_COOKIE_PATH,
        domain=COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        domain=COOKIE_DOMAIN,
    )


def _build_token_response(user: models.User, access_token: str, expires_at: datetime) -> JSONResponse:
    expires_in = max(0, int((expires_at - _now()).total_seconds()))
    payload: dict[str, Any] = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user_id": str(user.id),
        "email_verified": bool(user.email_verified_at),
    }
    response = JSONResponse(payload)
    _cache_busting_headers(response)
    return response


@router.post("/auth/login", response_model=schemas.Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate a user and return an access token."""

    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing username or password",
        )
    client_ip = get_client_ip(request)
    safe_ip = anonymize_ip(client_ip)
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        if _should_log_failure(client_ip or "unknown"):
            auth_logger.warning(
                "Authentication failed",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "login_failed",
                    "client_ip": safe_ip,
                    "auth_method": "password",
                    "auth_failure_reason": "invalid_credentials",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    login_time = _now()
    user.last_login_at = login_time
    user.last_active_at = login_time

    raw_refresh, refresh_record = issue_refresh_token(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
    )
    access_token, expires_at = create_access_token(str(user.id))
    set_user_context(str(user.id))
    db.commit()

    response = _build_token_response(user, access_token, expires_at)
    _set_refresh_cookie(response, raw_refresh, REFRESH_ABS_TTL)
    csrf_nonce = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, csrf_nonce, REFRESH_ABS_TTL)

    auth_logger.info(
        "Authentication successful",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "login_success",
            "client_ip": safe_ip,
            "auth_method": "password",
            "refresh_family_id": str(refresh_record.family_id),
        },
    )
    return response


@router.post("/auth/refresh", response_model=schemas.Token)
def refresh_token(request: Request, db: Session = Depends(get_db)):
    """Rotate the refresh token and issue a new access token."""

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    token_hash = hash_refresh_token(raw_refresh)
    token_record = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == token_hash)
        .with_for_update()
        .one_or_none()
    )
    now = _now()
    if not token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if token_record.rotated_at is not None:
        revoke_refresh_family(db, token_record.family_id, reason="reuse_detected", timestamp=now)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected")

    if token_record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    if refresh_token_expired(token_record, now=now):
        token_record.revoked_at = now
        token_record.revocation_reason = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user_agent = token_record.user_agent
    user = token_record.user

    token_record.rotated_at = now
    token_record.last_used_at = now

    raw_new_refresh, new_record = issue_refresh_token(
        db,
        user,
        family_id=token_record.family_id,
        user_agent=user_agent,
        absolute_expiry=token_record.expires_at,
    )
    new_record.last_used_at = now

    access_token, expires_at = create_access_token(str(user.id))
    set_user_context(str(user.id))
    db.commit()

    remaining_lifetime = max(1, int((token_record.expires_at - now).total_seconds()))
    response = _build_token_response(user, access_token, expires_at)
    _set_refresh_cookie(response, raw_new_refresh, remaining_lifetime)
    csrf_nonce = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, csrf_nonce, remaining_lifetime)
    return response


@router.post(
    "/auth/verification/resend",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=schemas.Message,
)
def resend_verification_email(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-issue an email verification token for the authenticated user."""

    if current_user.email_verified_at:
        return {"detail": "Your email address is already verified."}
    allowed, reason = can_issue_again(current_user)
    if not allowed:
        if reason == "cooldown":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="We recently sent a verification email. Please check your inbox.",
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily verification email limit reached. Try again tomorrow.",
        )

    token, code, _ = issue_verification_token(current_user)
    db.flush()
    enqueue_verification_email(background_tasks, current_user, token=token, code=code)
    db.commit()
    auth_logger.info(
        "Verification email reissued",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "verification_email_sent",
            "user_id": str(current_user.id),
        },
    )
    return {"detail": "We sent you a new verification email."}


@router.post(
    "/auth/verify",
    response_model=schemas.Message,
)
def verify_email(
    payload: schemas.EmailVerificationRequest,
    db: Session = Depends(get_db),
):
    """Validate a verification token or code and mark the user as verified."""

    user: models.User | None = None
    if payload.uid:
        user = db.get(models.User, payload.uid)
    if user is None and payload.email:
        user = get_user(db, payload.email)
    generic = {"detail": "If the account exists, the verification state was updated."}
    if user is None:
        return generic

    now = _now()
    if user.email_verified_at:
        return {"detail": "Email already verified."}
    if not user.verify_token_hash or not user.verify_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link or code is invalid or expired. Request a new email.",
        )
    if user.verify_token_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link or code is invalid or expired. Request a new email.",
        )

    matched = False
    if payload.token and token_matches(user, payload.token):
        matched = True
    elif payload.code and code_matches(user, payload.code):
        matched = True

    if not matched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link or code is invalid or expired. Request a new email.",
        )

    clear_verification_state(user, verified_at=now)
    db.flush()
    families = {
        token.family_id
        for token in db.query(models.RefreshToken)
        .filter(models.RefreshToken.user_id == user.id)
        .filter(models.RefreshToken.revoked_at.is_(None))
    }
    for family_id in families:
        revoke_refresh_family(
            db,
            family_id,
            reason="email_verified",
            timestamp=now,
        )
    db.commit()
    auth_logger.info(
        "Email verified",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "email_verified",
            "user_id": str(user.id),
        },
    )
    return {"detail": "Email verified."}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """Invalidate the current refresh token and clear cookies."""

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        token_hash = hash_refresh_token(raw_refresh)
        token_record = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.token_hash == token_hash)
            .one_or_none()
        )
        now = _now()
        if token_record:
            revoke_refresh_family(
                db,
                token_record.family_id,
                reason="logout",
                timestamp=now,
            )
            db.commit()
    _clear_cookies(response)
    _cache_busting_headers(response)
    return response

