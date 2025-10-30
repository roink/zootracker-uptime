"""Helpers for issuing and validating password reset tokens."""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from .. import models
from ..config import (
    APP_BASE_URL,
    PASSWORD_RESET_DAILY_LIMIT,
    PASSWORD_RESET_REQUEST_COOLDOWN,
    PASSWORD_RESET_TTL_MINUTES,
    TOKEN_PEPPER,
)
from .email_sender import (
    SMTPSettings,
    build_email,
    load_smtp_settings,
    send_email_via_smtp,
)

logger = logging.getLogger("app.password_reset")

_PEPPER = TOKEN_PEPPER.encode("utf-8")
_KIND = models.VerificationTokenKind.PASSWORD_RESET
_DAILY_WINDOW = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_secret(raw: str) -> str:
    """Return an HMAC-SHA256 hash of ``raw`` using the configured pepper."""

    digest = hmac.new(_PEPPER, raw.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def reset_token_identifier(raw: str) -> str:
    """Return a deterministic identifier for rate limiting a reset token."""

    return _hash_secret(raw)


def can_issue_password_reset(
    db: Session,
    user: models.User,
    *,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """Return whether another password reset email can be sent."""

    current = now or _now()
    last_token = (
        db.query(models.VerificationToken)
        .filter(models.VerificationToken.user_id == user.id)
        .filter(models.VerificationToken.kind == _KIND)
        .order_by(models.VerificationToken.created_at.desc())
        .first()
    )
    if last_token and (
        current - last_token.created_at
    ).total_seconds() < PASSWORD_RESET_REQUEST_COOLDOWN:
        return False, "cooldown"

    window_start = current - _DAILY_WINDOW
    recent_attempts = (
        db.query(models.VerificationToken)
        .filter(models.VerificationToken.user_id == user.id)
        .filter(models.VerificationToken.kind == _KIND)
        .filter(models.VerificationToken.created_at >= window_start)
        .count()
    )
    if recent_attempts >= PASSWORD_RESET_DAILY_LIMIT:
        return False, "limit"

    return True, None


def issue_password_reset_token(
    db: Session,
    user: models.User,
    *,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """Create a password reset token for ``user`` and persist its hash."""

    current = now or _now()
    token = secrets.token_urlsafe(32)
    expires_at = current + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)

    db.query(models.VerificationToken).filter(
        models.VerificationToken.user_id == user.id,
        models.VerificationToken.kind == _KIND,
        models.VerificationToken.consumed_at.is_(None),
    ).update(
        {models.VerificationToken.consumed_at: current},
        synchronize_session=False,
    )

    record = models.VerificationToken(
        user=user,
        kind=_KIND,
        token_hash=_hash_secret(token),
        code_hash=None,
        expires_at=expires_at,
        created_at=current,
    )
    db.add(record)
    return token, expires_at


def get_reset_token(
    db: Session,
    *,
    token: str,
) -> models.VerificationToken | None:
    """Return the password reset token matching ``token`` if it exists."""

    hashed = _hash_secret(token)
    return (
        db.query(models.VerificationToken)
        .filter(models.VerificationToken.kind == _KIND)
        .filter(models.VerificationToken.token_hash == hashed)
        .order_by(models.VerificationToken.created_at.desc())
        .first()
    )


def consume_reset_token(
    db: Session,
    record: models.VerificationToken,
    *,
    timestamp: datetime | None = None,
) -> None:
    """Mark ``record`` as consumed at ``timestamp``."""

    record.consumed_at = timestamp or _now()
    db.query(models.VerificationToken).filter(
        models.VerificationToken.user_id == record.user_id,
        models.VerificationToken.kind == _KIND,
        models.VerificationToken.id != record.id,
        models.VerificationToken.consumed_at.is_(None),
    ).update({models.VerificationToken.consumed_at: record.consumed_at}, synchronize_session=False)


def build_password_reset_email(
    user: models.User,
    *,
    token: str,
    expires_at: datetime,
) -> tuple[SMTPSettings, EmailMessage]:
    """Compose the password reset email for ``user``."""

    base_url = APP_BASE_URL.rstrip("/") or "http://localhost:5173"
    reset_url = f"{base_url}/reset-password?token={token}"
    remaining_minutes = max(1, int((expires_at - _now()).total_seconds() // 60))
    subject = "Reset your ZooTracker password"
    body = (
        f"Hi {user.name},\n\n"
        f"We received a request to reset the password for {user.email}.\n\n"
        "If you made this request, open the link below to choose a new password:\n\n"
        f"{reset_url}\n\n"
        f"The link expires in {remaining_minutes} minutes. If you did not request "
        "a password reset, you can safely ignore this email.\n\n"
        "— ZooTracker Accounts"
    )
    settings = load_smtp_settings(default_from="accounts@zootracker.app")
    message = build_email(
        subject=subject,
        from_addr=settings.from_addr,
        to_addr=user.email,
        body=body,
    )
    return settings, message


def build_password_reset_confirmation_email(
    user: models.User,
) -> tuple[SMTPSettings, EmailMessage]:
    """Compose the follow-up email sent after a successful password reset."""

    subject = "Your ZooTracker password was reset"
    body = (
        f"Hi {user.name},\n\n"
        "This is a confirmation that your ZooTracker password was just reset. "
        "If you did not perform this action, please reset your password again "
        "and contact support immediately.\n\n"
        "— ZooTracker Accounts"
    )
    settings = load_smtp_settings(default_from="accounts@zootracker.app")
    message = build_email(
        subject=subject,
        from_addr=settings.from_addr,
        to_addr=user.email,
        body=body,
    )
    return settings, message


def _send_email(
    background_tasks: BackgroundTasks,
    *,
    settings: SMTPSettings,
    message: EmailMessage,
    execute_immediately: bool,
    log_extra: dict[str, str],
    auth_error: tuple[str, str],
    ssl_retry: tuple[str, str],
    send_failure: tuple[str, str],
    immediate_log: str,
) -> None:
    """Deliver a password reset related email immediately or via background task."""

    if not settings.host:
        logger.error(
            "Email service misconfigured for password reset delivery",
            extra=log_extra,
        )
        return
    if execute_immediately:
        logger.info(immediate_log, extra=log_extra)
        try:
            send_email_via_smtp(
                settings=settings,
                message=message,
                logger=logger,
                auth_error=auth_error,
                ssl_retry=ssl_retry,
                send_failure=send_failure,
                log_extra=log_extra,
            )
        except Exception:
            logger.exception(
                "Immediate password reset email delivery failed",
                extra=log_extra,
            )
        return
    background_tasks.add_task(
        send_email_via_smtp,
        settings=settings,
        message=message,
        logger=logger,
        auth_error=auth_error,
        ssl_retry=ssl_retry,
        send_failure=send_failure,
        log_extra=log_extra,
    )


def enqueue_password_reset_email(
    background_tasks: BackgroundTasks,
    user: models.User,
    *,
    token: str,
    expires_at: datetime,
    execute_immediately: bool = False,
) -> None:
    """Schedule delivery of the password reset email."""

    settings, message = build_password_reset_email(
        user,
        token=token,
        expires_at=expires_at,
    )
    log_extra: dict[str, str] = {"password_reset_user_id": str(user.id)}
    _send_email(
        background_tasks,
        settings=settings,
        message=message,
        execute_immediately=execute_immediately,
        log_extra=log_extra,
        auth_error=(
            "SMTP authentication failed when sending password reset email",
            "password_reset_email_auth_failed",
        ),
        ssl_retry=(
            "SMTP SSL delivery failed for password reset email, retrying with STARTTLS",
            "password_reset_email_ssl_retry",
        ),
        send_failure=(
            "Failed to send password reset email",
            "password_reset_email_failed",
        ),
        immediate_log="Sending password reset email immediately",
    )


def enqueue_password_reset_confirmation(
    background_tasks: BackgroundTasks,
    user: models.User,
    *,
    execute_immediately: bool = False,
) -> None:
    """Notify the user that their password was changed."""

    settings, message = build_password_reset_confirmation_email(user)
    log_extra: dict[str, str] = {"password_reset_user_id": str(user.id)}
    _send_email(
        background_tasks,
        settings=settings,
        message=message,
        execute_immediately=execute_immediately,
        log_extra=log_extra,
        auth_error=(
            "SMTP authentication failed when sending password reset confirmation",
            "password_reset_confirmation_auth_failed",
        ),
        ssl_retry=(
            "SMTP SSL delivery failed for password reset confirmation, retrying with STARTTLS",
            "password_reset_confirmation_ssl_retry",
        ),
        send_failure=(
            "Failed to send password reset confirmation email",
            "password_reset_confirmation_failed",
        ),
        immediate_log="Sending password reset confirmation email immediately",
    )

