"""Contact form endpoint and supporting helpers."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import bleach

from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Request, Response, status

from .. import schemas
from ..logging import anonymize_ip
from ..rate_limit import enforce_contact_rate_limit
from ..utils.network import get_client_ip
from .deps import require_json


logger = logging.getLogger("app.api.contact")

router = APIRouter()


def _strip_crlf(value: str) -> str:
    """Remove carriage-return and line-feed characters from header values."""

    return value.replace("\r", "").replace("\n", "")


def _safe_ehlo(server) -> None:
    """Call ``EHLO`` on an SMTP server, tolerating light-weight fakes."""

    ehlo = getattr(server, "ehlo", None)
    if ehlo is None:
        return

    if not getattr(server, "local_hostname", None):
        try:
            server.local_hostname = "localhost"
        except Exception:  # pragma: no cover - defensive best-effort only
            return

    try:
        ehlo()
    except AttributeError:  # pragma: no cover - graceful degradation
        return


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

    context = ssl.create_default_context()
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    except AttributeError:  # pragma: no cover - Python < 3.7 compatibility
        pass

    safe_name = _strip_crlf(name)
    safe_reply_to = _strip_crlf(reply_to)
    email_msg = EmailMessage()
    email_msg["Subject"] = f"Contact form – {safe_name}"
    email_msg["From"] = from_addr
    email_msg["To"] = to_addr
    email_msg["Reply-To"] = safe_reply_to
    email_msg["Date"] = formatdate(localtime=True)
    msgid_domain = from_addr.split("@", 1)[1] if "@" in from_addr else None
    email_msg["Message-ID"] = make_msgid(domain=msgid_domain)
    email_msg.set_content(f"From: {safe_name} <{safe_reply_to}>\n\n{msg_text}")

    timeout_value = os.getenv("SMTP_TIMEOUT", "10")
    try:
        timeout = float(timeout_value)
    except ValueError:
        timeout = 10.0

    attempts: list[str] = []

    def _deliver(via_ssl: bool) -> None:
        label = "ssl" if via_ssl else "starttls"
        attempts.append(label)
        if via_ssl:
            server_factory = lambda: smtplib.SMTP_SSL(host, port, context=context, timeout=timeout)
            use_starttls = False
        else:
            server_factory = lambda: smtplib.SMTP(host, port, timeout=timeout)
            use_starttls = True

        with server_factory() as server:
            _safe_ehlo(server)
            if use_starttls:
                supports_starttls = False
                has_extn = getattr(server, "has_extn", None)
                if callable(has_extn):
                    try:
                        supports_starttls = bool(has_extn("starttls"))
                    except Exception:  # pragma: no cover - defensive logging
                        supports_starttls = False
                if supports_starttls:
                    starttls = getattr(server, "starttls", None)
                    if callable(starttls):
                        starttls(context=context)
                        _safe_ehlo(server)
            if user and password:
                server.login(user, password)
            server.send_message(email_msg)

    try:
        _deliver(use_ssl)
        return
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed when sending contact email",
            extra={
                "event_dataset": "zoo-tracker-api.app",
                "event_action": "contact_email_auth_failed",
                "smtp_attempts": ",".join(attempts),
            },
            exc_info=True,
        )
        return
    except Exception:
        if use_ssl:
            logger.warning(
                "SMTP SSL delivery failed, retrying with STARTTLS",
                extra={
                    "event_dataset": "zoo-tracker-api.app",
                    "event_action": "contact_email_ssl_retry",
                },
                exc_info=True,
            )
            try:
                _deliver(False)
                return
            except smtplib.SMTPAuthenticationError:
                logger.error(
                    "SMTP authentication failed when sending contact email",
                    extra={
                        "event_dataset": "zoo-tracker-api.app",
                        "event_action": "contact_email_auth_failed",
                        "smtp_attempts": ",".join(attempts),
                    },
                    exc_info=True,
                )
                return
            except Exception:
                logger.error(
                    "Failed to send contact email",
                    extra={
                        "event_dataset": "zoo-tracker-api.app",
                        "event_action": "contact_email_failed",
                        "smtp_attempts": ",".join(attempts),
                    },
                    exc_info=True,
                )
                return
        logger.error(
            "Failed to send contact email",
            extra={
                "event_dataset": "zoo-tracker-api.app",
                "event_action": "contact_email_failed",
                "smtp_attempts": ",".join(attempts),
            },
            exc_info=True,
        )


def _get_smtp_settings() -> tuple[str, int, bool, str | None, str | None, str, str]:
    """Read SMTP configuration from environment variables."""

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_SSL", "").lower() in {"1", "true", "yes"}
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", "contact@zootracker.app")
    to_addr = os.getenv("CONTACT_EMAIL", "contact@zootracker.app")
    return host, port, use_ssl, user, password, from_addr, to_addr


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
