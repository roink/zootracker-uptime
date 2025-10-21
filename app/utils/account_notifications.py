"""Account notification helpers such as duplicate sign-up emails."""

from __future__ import annotations

import logging

from fastapi import BackgroundTasks

from .. import models
from ..config import APP_BASE_URL
from .email_sender import build_email, load_smtp_settings, send_email_via_smtp

logger = logging.getLogger("app.account_notifications")


def build_existing_signup_notice_email(user: models.User):
    """Compose the email sent when a signup uses an existing address."""

    base_url = APP_BASE_URL.rstrip("/") or "http://localhost:5173"
    login_url = f"{base_url}/login"
    name = user.name or "there"
    subject = "You already have a ZooTracker account"
    body = (
        f"Hi {name},\n\n"
        "Someone just tried to create a ZooTracker account with this email address.\n\n"
        "If that was you, you can sign in using your existing account:\n"
        f"{login_url}\n\n"
        "Forgot your password? Use the same page to start a reset.\n\n"
        "If you didn't start this request, no action is needed and no new account "
        "was created.\n\n"
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


def enqueue_existing_signup_notice(
    background_tasks: BackgroundTasks,
    user: models.User,
    *,
    execute_immediately: bool = False,
) -> None:
    """Schedule delivery of the duplicate-signup notice email."""

    settings, message = build_existing_signup_notice_email(user)
    log_extra = {"existing_account_user_id": str(user.id)}
    if not settings.host:
        logger.error(
            "Email service misconfigured for existing signup notice",
            extra=log_extra,
        )
        return
    if execute_immediately:
        logger.info(
            "Sending existing signup notice email immediately",
            extra=log_extra,
        )
        try:
            send_email_via_smtp(
                settings=settings,
                message=message,
                logger=logger,
                auth_error=(
                    "SMTP authentication failed when sending existing signup notice",
                    "existing_signup_notice_auth_failed",
                ),
                ssl_retry=(
                    "SMTP SSL delivery failed for existing signup notice, retrying with STARTTLS",
                    "existing_signup_notice_ssl_retry",
                ),
                send_failure=(
                    "Failed to send existing signup notice email",
                    "existing_signup_notice_failed",
                ),
                log_extra=log_extra,
            )
        except Exception:
            logger.exception(
                "Immediate existing signup notice delivery failed",
                extra=log_extra,
            )
        return
    background_tasks.add_task(
        send_email_via_smtp,
        settings=settings,
        message=message,
        logger=logger,
        auth_error=(
            "SMTP authentication failed when sending existing signup notice",
            "existing_signup_notice_auth_failed",
        ),
        ssl_retry=(
            "SMTP SSL delivery failed for existing signup notice, retrying with STARTTLS",
            "existing_signup_notice_ssl_retry",
        ),
        send_failure=(
            "Failed to send existing signup notice email",
            "existing_signup_notice_failed",
        ),
        log_extra=log_extra,
    )

