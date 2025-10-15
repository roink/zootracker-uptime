"""Helpers for issuing and validating email verification tokens."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks

from .. import models
from ..config import (
    APP_BASE_URL,
    EMAIL_VERIFICATION_DAILY_LIMIT,
    EMAIL_VERIFICATION_RESEND_COOLDOWN,
    EMAIL_VERIFICATION_TTL_MINUTES,
    TOKEN_PEPPER,
)
from .email_sender import build_email, load_smtp_settings, send_email_via_smtp

logger = logging.getLogger("app.email_verification")

_PEPPER = TOKEN_PEPPER.encode("utf-8")
_DAILY_WINDOW = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_secret(raw: str) -> str:
    """Return an HMAC-SHA256 hash of ``raw`` using the configured pepper."""

    digest = hmac.new(_PEPPER, raw.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def _format_code() -> str:
    """Generate a six digit verification code."""

    return f"{secrets.randbelow(1_000_000):06d}"


def issue_verification_token(
    user: models.User,
    *,
    now: datetime | None = None,
) -> tuple[str, str, datetime]:
    """Create a verification token/code pair and persist hashes on ``user``."""

    current = now or _now()
    token = secrets.token_urlsafe(32)
    code = _format_code()
    expires_at = current + timedelta(minutes=EMAIL_VERIFICATION_TTL_MINUTES)

    user.verify_token_hash = _hash_secret(token)
    user.verify_code_hash = _hash_secret(code)
    user.verify_token_expires_at = expires_at

    last_sent = user.last_verify_sent_at
    if not last_sent or current - last_sent >= _DAILY_WINDOW:
        user.verify_attempts = 1
    else:
        user.verify_attempts = (user.verify_attempts or 0) + 1
    user.last_verify_sent_at = current

    return token, code, expires_at


def can_issue_again(user: models.User, *, now: datetime | None = None) -> tuple[bool, str | None]:
    """Return whether another verification email can be sent and a failure reason."""

    current = now or _now()
    if user.last_verify_sent_at and (
        current - user.last_verify_sent_at
    ).total_seconds() < EMAIL_VERIFICATION_RESEND_COOLDOWN:
        return False, "cooldown"
    if (
        user.last_verify_sent_at
        and current - user.last_verify_sent_at < _DAILY_WINDOW
        and (user.verify_attempts or 0) >= EMAIL_VERIFICATION_DAILY_LIMIT
    ):
        return False, "limit"
    return True, None


def build_verification_email(
    user: models.User,
    *,
    token: str,
    code: str,
):
    """Compose the plain-text verification email for ``user``."""

    base_url = APP_BASE_URL.rstrip("/") or "http://localhost:5173"
    verify_url = f"{base_url}/verify?uid={user.id}&token={token}"
    subject = (
        "Verify your email for ZooTracker "
        f"(valid for {EMAIL_VERIFICATION_TTL_MINUTES} minutes)"
    )
    body = (
        f"Hi {user.name},\n\n"
        f"We're verifying the email address {user.email}.\n\n"
        "Thanks for creating a ZooTracker account. Please confirm your email "
        "by opening this link:\n\n"
        f"{verify_url}\n\n"
        "Or enter this verification code: "
        f"{code}\n\n"
        f"The link and code expire in {EMAIL_VERIFICATION_TTL_MINUTES} minutes. "
        "If you did not request this, you can safely ignore the email.\n\n"
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


def enqueue_verification_email(
    background_tasks: BackgroundTasks,
    user: models.User,
    *,
    token: str,
    code: str,
) -> None:
    """Schedule delivery of the verification email if SMTP is configured."""

    settings, message = build_verification_email(user, token=token, code=code)
    if not settings.host:
        logger.error(
            "Email service misconfigured for verification email",
            extra={"verification_user_id": str(user.id)},
        )
        return
    background_tasks.add_task(
        send_email_via_smtp,
        settings=settings,
        message=message,
        logger=logger,
        auth_error=(
            "SMTP authentication failed when sending verification email",
            "verification_email_auth_failed",
        ),
        ssl_retry=(
            "SMTP SSL delivery failed for verification email, retrying with STARTTLS",
            "verification_email_ssl_retry",
        ),
        send_failure=(
            "Failed to send verification email",
            "verification_email_failed",
        ),
        log_extra={"verification_user_id": str(user.id)},
    )


def token_matches(user: models.User, raw: str | None) -> bool:
    """Return ``True`` when ``raw`` matches the stored token hash."""

    if not raw or not user.verify_token_hash:
        return False
    return hmac.compare_digest(user.verify_token_hash, _hash_secret(raw))


def code_matches(user: models.User, raw: str | None) -> bool:
    """Return ``True`` when ``raw`` matches the stored code hash."""

    if not raw or not user.verify_code_hash:
        return False
    return hmac.compare_digest(user.verify_code_hash, _hash_secret(raw))


def clear_verification_state(user: models.User, *, verified_at: datetime | None = None) -> None:
    """Mark the user as verified and reset verification tracking fields."""

    timestamp = verified_at or _now()
    user.email_verified_at = timestamp
    user.verify_token_hash = None
    user.verify_code_hash = None
    user.verify_token_expires_at = None
    user.verify_attempts = 0
    user.last_verify_sent_at = None
