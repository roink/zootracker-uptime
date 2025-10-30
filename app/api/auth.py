"""Authentication API endpoints."""

from __future__ import annotations

import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import anyio
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import ORJSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import (
    create_access_token,
    get_current_user,
    get_user,
    hash_password,
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
from ..rate_limit import (
    enforce_password_reset_request_limit,
    enforce_password_reset_token_limit,
    enforce_verification_resend_limit,
    enforce_verify_rate_limit,
    register_failed_password_reset_attempt,
    register_failed_verification_attempt,
)
from ..utils.email_verification import (
    can_issue_again,
    clear_verification_state,
    code_matches,
    enqueue_verification_email,
    get_latest_token,
    issue_verification_token,
    token_matches,
)
from ..utils.network import get_client_ip
from ..utils.password_reset import (
    can_issue_password_reset,
    consume_reset_token,
    enqueue_password_reset_confirmation,
    enqueue_password_reset_email,
    get_reset_token,
    issue_password_reset_token,
    reset_token_identifier,
)

router = APIRouter()

_db_dependency = Depends(get_db)
_oauth_form_dependency = Depends()
_current_user_dependency = Depends(get_current_user)


auth_logger = logging.getLogger("app.auth")

_FAILURE_WINDOW_SECONDS = 60
_FAILURE_LOG_LIMIT = 10
_failure_attempts: dict[str, deque[float]] = defaultdict(deque)

_GENERIC_RESET_DETAIL = "If the reset token is valid, your password has been updated."
_GENERIC_RESET_PAYLOAD = {"detail": _GENERIC_RESET_DETAIL}

_RESET_INVALID_MESSAGE = (
    "This password reset link is invalid. Request a new password reset email to continue."
)
_RESET_CONSUMED_MESSAGE = (
    "This password reset link has already been used. Request a new password reset email to continue."
)
_RESET_EXPIRED_MESSAGE = (
    "This password reset link has expired. Request a new password reset email to continue."
)

_RESET_FAILURE_RESPONSES: dict[str, tuple[int, str, str]] = {
    "token_missing": (
        status.HTTP_404_NOT_FOUND,
        "invalid",
        _RESET_INVALID_MESSAGE,
    ),
    "token_consumed": (
        status.HTTP_409_CONFLICT,
        "consumed",
        _RESET_CONSUMED_MESSAGE,
    ),
    "token_expired": (
        status.HTTP_410_GONE,
        "expired",
        _RESET_EXPIRED_MESSAGE,
    ),
    "user_missing": (
        status.HTTP_404_NOT_FOUND,
        "invalid",
        _RESET_INVALID_MESSAGE,
    ),
}

_RESET_FAILURE_LOG_MESSAGES = {
    "token_missing": "Password reset attempt with missing token",
    "token_consumed": "Password reset attempt with consumed token",
    "token_expired": "Password reset attempt with expired token",
    "user_missing": "Password reset attempt for missing user",
}


def _classify_reset_token(
    token_record: models.VerificationToken | None,
    *,
    now: datetime,
) -> str | None:
    if token_record is None:
        return "token_missing"
    if token_record.consumed_at is not None:
        return "token_consumed"
    if token_record.expires_at < now:
        return "token_expired"
    if token_record.user is None:
        return "user_missing"
    return None


async def _build_reset_failure_response(
    request: Request,
    *,
    identifier: str,
    reason: str,
    log_message: str,
    client_ip: str | None,
    user_id: str | None = None,
) -> ORJSONResponse:
    extra: dict[str, Any] = {
        "event_dataset": "zoo-tracker-api.auth",
        "event_action": "password_reset_failed",
        "password_reset_failure_reason": reason,
    }
    if user_id:
        extra["user_id"] = user_id
    try:
        await register_failed_password_reset_attempt(
            request,
            identifier=identifier,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            auth_logger.warning(
                "Password reset failure rate limited",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "password_reset_rate_limited",
                    "rate_limit_scope": "token_failure",
                    "client_ip": client_ip,
                    "password_reset_failure_reason": reason,
                },
            )
            payload = {**_GENERIC_RESET_PAYLOAD, "status": "rate_limited"}
            response = ORJSONResponse(
                payload,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=exc.headers,
            )
            _cache_busting_headers(response)
            return response
        raise
    auth_logger.warning(log_message, extra=extra)
    status_code, status_name, detail = _RESET_FAILURE_RESPONSES.get(
        reason,
        (status.HTTP_400_BAD_REQUEST, "invalid", _GENERIC_RESET_DETAIL),
    )
    payload = {"detail": detail, "status": status_name}
    response = ORJSONResponse(payload, status_code=status_code)
    _cache_busting_headers(response)
    return response


def _should_log_failure(ip_key: str) -> bool:
    now = time.monotonic()
    history = _failure_attempts[ip_key]
    while history and now - history[0] > _FAILURE_WINDOW_SECONDS:
        history.popleft()
    history.append(now)
    return len(history) <= _FAILURE_LOG_LIMIT


def _now() -> datetime:
    return datetime.now(UTC)


_CACHE_BUSTER_HEADER_VALUES = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _cache_busting_headers(response: Response) -> None:
    response.headers.update(_CACHE_BUSTER_HEADER_VALUES)


def _cache_busting_http_exception(status_code: int, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers=_CACHE_BUSTER_HEADER_VALUES.copy(),
    )


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


def _build_token_response(user: models.User, access_token: str, expires_at: datetime) -> ORJSONResponse:
    expires_in = max(0, int((expires_at - _now()).total_seconds()))
    payload: dict[str, Any] = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user_id": str(user.id),
        "email_verified": bool(user.email_verified_at),
    }
    response = ORJSONResponse(payload)
    _cache_busting_headers(response)
    return response


@router.post("/auth/login", response_model=schemas.Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = _oauth_form_dependency,
    db: Session = _db_dependency,
) -> ORJSONResponse:
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

    if not user.email_verified_at:
        auth_logger.info(
            "Login blocked for unverified email",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "login_blocked",
                "client_ip": safe_ip,
                "auth_method": "password",
                "auth_failure_reason": "email_unverified",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address has not been verified yet.",
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
def refresh_token(request: Request, db: Session = _db_dependency) -> ORJSONResponse:
    """Rotate the refresh token and issue a new access token."""

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise _cache_busting_http_exception(
            status.HTTP_403_FORBIDDEN, "Invalid CSRF token"
        )

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise _cache_busting_http_exception(
            status.HTTP_401_UNAUTHORIZED, "Missing refresh token"
        )

    token_hash = hash_refresh_token(raw_refresh)
    token_record = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == token_hash)
        .with_for_update()
        .one_or_none()
    )
    now = _now()
    if not token_record:
        raise _cache_busting_http_exception(
            status.HTTP_401_UNAUTHORIZED, "Invalid refresh token"
        )

    if token_record.rotated_at is not None:
        revoke_refresh_family(db, token_record.family_id, reason="reuse_detected", timestamp=now)
        db.commit()
        raise _cache_busting_http_exception(
            status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected"
        )

    if token_record.revoked_at is not None:
        raise _cache_busting_http_exception(
            status.HTTP_401_UNAUTHORIZED, "Refresh token revoked"
        )

    if refresh_token_expired(token_record, now=now):
        token_record.revoked_at = now
        token_record.revocation_reason = "expired"
        db.commit()
        raise _cache_busting_http_exception(
            status.HTTP_401_UNAUTHORIZED, "Refresh token expired"
        )

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
    current_user: models.User = _current_user_dependency,
    db: Session = _db_dependency,
) -> schemas.Message:
    """Re-issue an email verification token for the authenticated user."""

    if current_user.email_verified_at:
        return schemas.Message(detail="Your email address is already verified.")
    allowed, reason = can_issue_again(db, current_user)
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

    token, code, _ = issue_verification_token(db, current_user)
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
    return schemas.Message(detail="We sent you a new verification email.")


@router.post(
    "/auth/verification/request-resend",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=schemas.Message,
)
def request_verification_resend(
    request: Request,
    payload: schemas.VerificationResendRequest,
    background_tasks: BackgroundTasks,
    db: Session = _db_dependency,
) -> schemas.Message | ORJSONResponse:
    """Allow users to request another verification email without authentication."""

    generic_payload = {
        "detail": "If the account exists, verification instructions will be sent."
    }
    try:
        anyio.from_thread.run(
            enforce_verification_resend_limit, request, payload.email
        )
    except HTTPException as exc:  # pragma: no cover - defensive branch
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            auth_logger.info(
                "Verification resend skipped",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "verification_resend_throttled",
                    "verification_throttle_reason": "rate_limit",
                },
            )
            return ORJSONResponse(
                generic_payload,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=exc.headers,
            )
        raise
    user = get_user(db, payload.email)
    if not user or user.email_verified_at:
        auth_logger.info(
            "Anonymous verification resend request",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "verification_resend_requested",
                "email_known_user": bool(user),
                "email_verified": bool(user and user.email_verified_at),
            },
        )
        return schemas.Message(**generic_payload)

    allowed, reason = can_issue_again(db, user)
    if not allowed:
        auth_logger.info(
            "Verification resend skipped",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "verification_resend_throttled",
                "user_id": str(user.id),
                "verification_throttle_reason": reason or "unknown",
            },
        )
        return schemas.Message(**generic_payload)

    token, code, _ = issue_verification_token(db, user)
    db.flush()
    enqueue_verification_email(
        background_tasks,
        user,
        token=token,
        code=code,
        execute_immediately=True,
    )
    db.commit()
    auth_logger.info(
        "Verification email reissued anonymously",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "verification_email_sent",
            "user_id": str(user.id),
            "trigger": "anonymous_resend",
        },
    )
    return schemas.Message(**generic_payload)


@router.post(
    "/auth/verify",
    response_model=schemas.Message,
)
async def verify_email(
    request: Request,
    payload: schemas.EmailVerificationRequest,
    db: Session = _db_dependency,
) -> schemas.Message | ORJSONResponse:
    """Validate a verification token or code and mark the user as verified."""

    identifier: str | None = None
    if payload.uid:
        identifier = payload.uid
    elif payload.email:
        identifier = payload.email
    await enforce_verify_rate_limit(request, identifier=identifier)

    generic_payload = {
        "detail": "If the account exists, the verification state was updated."
    }

    def _generic_response(
        *,
        status_code: int = status.HTTP_202_ACCEPTED,
        headers: Mapping[str, str] | None = None,
    ) -> ORJSONResponse:
        response = ORJSONResponse(generic_payload, status_code=status_code, headers=headers)
        _cache_busting_headers(response)
        return response

    generic_response = _generic_response()

    user: models.User | None = None
    if payload.uid:
        try:
            uid_value = uuid.UUID(payload.uid)
        except ValueError:
            return generic_response
        user = db.get(models.User, uid_value)
    if user is None and payload.email:
        user = get_user(db, payload.email)
    if user is None:
        return generic_response

    now = _now()
    if user.email_verified_at:
        return generic_response
    token_record = get_latest_token(db, user)
    if token_record is None or token_record.consumed_at is not None:
        auth_logger.warning(
            "Verification attempt missing active token",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "email_verification_failed",
                "user_id": str(user.id),
                "verification_failure_reason": "token_missing",
            },
        )
        return generic_response
    if token_record.expires_at < now:
        auth_logger.warning(
            "Verification attempt with expired token",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "email_verification_failed",
                "user_id": str(user.id),
                "verification_failure_reason": "token_expired",
            },
        )
        return generic_response

    matched = bool(
        (payload.token and token_matches(token_record, payload.token))
        or (payload.code and code_matches(token_record, payload.code))
    )

    if not matched:
        await register_failed_verification_attempt(request, identifier=identifier)
        auth_logger.warning(
            "Verification attempt with invalid secret",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "email_verification_failed",
                "user_id": str(user.id),
                "verification_failure_reason": "secret_mismatch",
            },
        )
        return generic_response

    clear_verification_state(db, user, verified_at=now)
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
    return schemas.Message(detail="Email verified.")


@router.post(
    "/auth/password/forgot",
    response_model=schemas.Message,
)
async def request_password_reset(
    request: Request,
    payload: schemas.PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = _db_dependency,
) -> ORJSONResponse:
    """Handle anonymous password reset requests without leaking account status."""

    generic = {
        "detail": "If an account exists for that email, we'll send password reset instructions shortly.",
    }

    def _build_generic_response(
        *, status_code: int = status.HTTP_202_ACCEPTED, headers: dict[str, str] | None = None
    ) -> ORJSONResponse:
        response = ORJSONResponse(generic, status_code=status_code, headers=headers)
        _cache_busting_headers(response)
        return response

    generic_response = _build_generic_response()

    try:
        await enforce_password_reset_request_limit(request, identifier=payload.email)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            auth_logger.warning(
                "Password reset request rate limited",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "password_reset_rate_limited",
                    "rate_limit_scope": "request",
                    "client_ip": anonymize_ip(get_client_ip(request)),
                },
            )
            return _build_generic_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=exc.headers,
            )
        raise

    user = get_user(db, payload.email)
    if not user or not user.email_verified_at:
        auth_logger.info(
            "Anonymous password reset request",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "password_reset_requested",
                "email_known_user": bool(user),
                "email_verified": bool(user and user.email_verified_at),
            },
        )
        return generic_response

    allowed, reason = can_issue_password_reset(db, user)
    if not allowed:
        auth_logger.info(
            "Password reset request throttled",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "password_reset_throttled",
                "user_id": str(user.id),
                "password_reset_throttle_reason": reason or "unknown",
            },
        )
        return generic_response

    token, expires_at = issue_password_reset_token(db, user)
    db.flush()
    enqueue_password_reset_email(
        background_tasks,
        user,
        token=token,
        expires_at=expires_at,
        execute_immediately=True,
    )
    db.commit()
    auth_logger.info(
        "Password reset email issued",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "password_reset_email_sent",
            "user_id": str(user.id),
        },
    )
    return generic_response


@router.post(
    "/auth/password/reset",
    response_model=schemas.Message,
)
async def reset_password(
    request: Request,
    payload: schemas.PasswordResetConfirm,
    background_tasks: BackgroundTasks,
    db: Session = _db_dependency,
) -> ORJSONResponse:
    """Validate a reset token and persist a new password, revealing status on error."""

    generic_response = ORJSONResponse(
        _GENERIC_RESET_PAYLOAD.copy(),
        status_code=status.HTTP_202_ACCEPTED,
    )
    _cache_busting_headers(generic_response)

    token_identifier = reset_token_identifier(payload.token)
    client_ip = anonymize_ip(get_client_ip(request))

    try:
        await enforce_password_reset_token_limit(
            request,
            identifier=token_identifier,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            auth_logger.warning(
                "Password reset token submission rate limited",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "password_reset_rate_limited",
                    "rate_limit_scope": "token",
                    "client_ip": client_ip,
                },
            )
            response_payload = {**_GENERIC_RESET_PAYLOAD, "status": "rate_limited"}
            response = ORJSONResponse(
                response_payload,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=exc.headers,
            )
            _cache_busting_headers(response)
            return response
        raise

    token_record = get_reset_token(db, token=payload.token)
    now = _now()
    failure_reason = _classify_reset_token(token_record, now=now)
    if failure_reason:
        user_id = str(token_record.user_id) if token_record else None
        return await _build_reset_failure_response(
            request,
            identifier=token_identifier,
            reason=failure_reason,
            log_message=_RESET_FAILURE_LOG_MESSAGES[failure_reason],
            client_ip=client_ip,
            user_id=user_id,
        )

    assert token_record is not None
    user = token_record.user

    user.password_hash = hash_password(payload.password)
    user.last_active_at = now
    consume_reset_token(db, token_record, timestamp=now)

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
            reason="password_reset",
            timestamp=now,
        )

    db.flush()
    enqueue_password_reset_confirmation(
        background_tasks,
        user,
        execute_immediately=True,
    )
    db.commit()
    auth_logger.info(
        "Password reset completed",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "password_reset_completed",
            "user_id": str(user.id),
        },
    )
    return generic_response


@router.get(
    "/auth/password/reset/status",
    response_model=schemas.PasswordResetTokenStatus,
)
async def get_password_reset_status(
    request: Request,
    token: str = Query(..., min_length=1, max_length=512),
    db: Session = _db_dependency,
) -> ORJSONResponse:
    """Return the current status of a password reset token."""

    trimmed_token = token.strip()
    token_identifier = reset_token_identifier(trimmed_token)
    client_ip = anonymize_ip(get_client_ip(request))

    try:
        await enforce_password_reset_token_limit(
            request,
            identifier=token_identifier,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            auth_logger.warning(
                "Password reset token status rate limited",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "password_reset_rate_limited",
                    "rate_limit_scope": "token_status",
                    "client_ip": client_ip,
                },
            )
            payload = {**_GENERIC_RESET_PAYLOAD, "status": "rate_limited"}
            response = ORJSONResponse(
                payload,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=exc.headers,
            )
            _cache_busting_headers(response)
            return response
        raise

    token_record = get_reset_token(db, token=trimmed_token)
    now = _now()
    failure_reason = _classify_reset_token(token_record, now=now)
    if failure_reason:
        user_id = str(token_record.user_id) if token_record else None
        return await _build_reset_failure_response(
            request,
            identifier=token_identifier,
            reason=failure_reason,
            log_message=_RESET_FAILURE_LOG_MESSAGES[failure_reason],
            client_ip=client_ip,
            user_id=user_id,
        )

    if token_record:
        auth_logger.info(
            "Password reset token validated",
            extra={
                "event_dataset": "zoo-tracker-api.auth",
                "event_action": "password_reset_token_validated",
                "user_id": str(token_record.user_id),
            },
        )
    response = ORJSONResponse({"status": "valid"})
    _cache_busting_headers(response)
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = _db_dependency) -> Response:
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

