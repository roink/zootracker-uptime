"""Contact form endpoint and supporting helpers."""

from __future__ import annotations

import logging
import os

import bleach

from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Request, Response, status

from .. import schemas
from ..logging import anonymize_ip
from ..rate_limit import enforce_contact_rate_limit
from ..utils.email_sender import (
    SMTPSettings,
    build_email,
    load_smtp_settings,
    send_email_via_smtp,
)
from ..utils.network import get_client_ip
from .deps import require_json


logger = logging.getLogger("app.api.contact")

router = APIRouter()


def _strip_crlf(value: str) -> str:
    """Remove carriage-return and line-feed characters from header values."""

    return value.replace("\r", "").replace("\n", "")






def _set_request_id_header(response: Response, request: Request) -> None:
    """Copy the request id header onto the response if present."""

    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id


def _send_contact_email(
    host: str,
    port: int,
    use_ssl: bool,
    user: str | None,
    password: str | None,
    from_addr: str,
    to_addr: str,
    reply_to: str,
    name: str,
    msg_text: str,
) -> None:
    """Send the contact email synchronously in a background task."""

    safe_name = _strip_crlf(name)
    safe_reply_to = _strip_crlf(reply_to)
    body = f"From: {safe_name} <{safe_reply_to}>\n\n{msg_text}"

    timeout_value = os.getenv("SMTP_TIMEOUT", "10")
    try:
        timeout = float(timeout_value)
    except ValueError:
        timeout = 10.0

    settings = SMTPSettings(
        host=host,
        port=port,
        use_ssl=use_ssl,
        user=user,
        password=password,
        from_addr=from_addr,
        timeout=timeout,
    )

    message = build_email(
        subject=f"Contact form – {safe_name}",
        from_addr=from_addr,
        to_addr=to_addr,
        body=body,
        reply_to=safe_reply_to,
    )

    send_email_via_smtp(
        settings=settings,
        message=message,
        logger=logger,
        auth_error=(
            "SMTP authentication failed when sending contact email",
            "contact_email_auth_failed",
        ),
        ssl_retry=(
            "SMTP SSL delivery failed, retrying with STARTTLS",
            "contact_email_ssl_retry",
        ),
        send_failure=(
            "Failed to send contact email",
            "contact_email_failed",
        ),
    )

def _get_smtp_settings() -> tuple[str | None, int, bool, str | None, str | None, str, str]:
    """Retrieve SMTP configuration values from the environment."""

    settings = load_smtp_settings(default_from="contact@zootracker.app")
    to_addr = os.getenv("CONTACT_EMAIL", "contact@zootracker.app")
    return (
        settings.host,
        settings.port,
        settings.use_ssl,
        settings.user,
        settings.password,
        settings.from_addr,
        to_addr,
    )


@router.post(
    "/contact",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_json), Depends(enforce_contact_rate_limit)],
)
def send_contact(
    message: schemas.ContactMessage,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Send a contact message via email and log the submission."""

    ua = request.headers.get("User-Agent", "unknown")
    name = bleach.clean(message.name, tags=[], strip=True)
    msg_text = bleach.clean(message.message, tags=[], strip=True)
    ip = get_client_ip(request)
    safe_ip = getattr(request.state, "client_ip_logged", anonymize_ip(ip))
    email_domain = message.email.split("@", 1)[1] if "@" in message.email else "unknown"
    logger.info(
        "Contact submission received",
        extra={
            "event_dataset": "zoo-tracker-api.app",
            "event_action": "contact_submitted",
            "client_ip": safe_ip,
            "user_agent": ua,
            "contact_email_domain": email_domain,
            "contact_message_length": len(msg_text),
        },
    )

    host, port, use_ssl, user, password, from_addr, to_addr = _get_smtp_settings()
    if not host or not to_addr:
        logger.error(
            "Email service misconfigured",
            extra={
                "event_dataset": "zoo-tracker-api.app",
                "event_action": "contact_email_missing_config",
                "http_status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service misconfigured",
        )

    background_tasks.add_task(
        _send_contact_email,
        host,
        port,
        use_ssl,
        user,
        password,
        from_addr,
        to_addr,
        message.email,
        name,
        msg_text,
    )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    remaining = getattr(request.state, "rate_limit_remaining", None)
    if remaining is not None:
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    _set_request_id_header(response, request)
    return response


__all__ = [
    "router",
    "_send_contact_email",
]
