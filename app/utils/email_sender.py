"""Utilities for constructing and delivering SMTP email messages."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any


@dataclass(slots=True)
class SMTPSettings:
    """Runtime configuration for delivering emails via SMTP."""

    host: str | None
    port: int
    use_ssl: bool
    user: str | None
    password: str | None
    from_addr: str
    timeout: float


def load_smtp_settings(*, default_from: str) -> SMTPSettings:
    """Load SMTP configuration from environment variables."""

    host = os.getenv("SMTP_HOST")
    port_str = os.getenv("SMTP_PORT", "587")
    try:
        port = int(port_str)
    except ValueError:
        port = 587
    use_ssl = os.getenv("SMTP_SSL", "").strip().lower() in {"1", "true", "yes", "on"}
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", default_from)
    timeout_value = os.getenv("SMTP_TIMEOUT", "10")
    try:
        timeout = float(timeout_value)
    except ValueError:
        timeout = 10.0
    return SMTPSettings(
        host=host,
        port=port,
        use_ssl=use_ssl,
        user=user,
        password=password,
        from_addr=from_addr,
        timeout=timeout,
    )


def build_email(
    *,
    subject: str,
    from_addr: str,
    to_addr: str,
    body: str,
    reply_to: str | None = None,
) -> EmailMessage:
    """Create a simple plain text email message."""

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_addr
    message["Date"] = formatdate(localtime=True)
    # Mark messages as automated to avoid responder loops and suppress OOO replies.
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    domain = from_addr.split("@", 1)[1] if "@" in from_addr else None
    message["Message-ID"] = make_msgid(domain=domain)
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)
    return message


def _safe_ehlo(server: Any) -> None:
    """Invoke EHLO if supported by the SMTP server implementation."""

    ehlo = getattr(server, "ehlo", None)
    if ehlo is None:
        return
    if not getattr(server, "local_hostname", None):
        try:
            server.local_hostname = "localhost"
        except Exception:  # pragma: no cover - best effort fallback
            return
    try:
        ehlo()
    except AttributeError:  # pragma: no cover - defensive guard
        return


def _build_log_extra(
    *,
    base: dict[str, Any] | None,
    attempts: list[str],
    action: str,
) -> dict[str, Any]:
    extra = {
        "event_dataset": "zoo-tracker-api.app",
        "event_action": action,
        "smtp_attempts": ",".join(attempts),
    }
    if base:
        extra.update(base)
    return extra


def send_email_via_smtp(
    *,
    settings: SMTPSettings,
    message: EmailMessage,
    logger: logging.Logger,
    auth_error: tuple[str, str],
    ssl_retry: tuple[str, str],
    send_failure: tuple[str, str],
    log_extra: dict[str, Any] | None = None,
) -> None:
    """Deliver ``message`` using the provided SMTP settings with robust logging."""

    context = ssl.create_default_context()
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    except AttributeError:  # pragma: no cover - Python < 3.7 compatibility
        pass

    attempts: list[str] = []

    host = settings.host
    if not host:
        logger.error(
            send_failure[0],
            extra=_build_log_extra(
                base=log_extra,
                attempts=attempts,
                action=send_failure[1],
            ),
        )
        return

    def _deliver(via_ssl: bool) -> None:
        label = "ssl" if via_ssl else "starttls"
        attempts.append(label)
        if via_ssl:
            def factory() -> smtplib.SMTP:
                return smtplib.SMTP_SSL(
                    host,
                    settings.port,
                    context=context,
                    timeout=settings.timeout,
                )
            use_starttls = False
        else:
            def factory() -> smtplib.SMTP:
                return smtplib.SMTP(
                    host,
                    settings.port,
                    timeout=settings.timeout,
                )
            use_starttls = True

        with factory() as server:
            _safe_ehlo(server)
            if use_starttls:
                supports_starttls = False
                has_extn = getattr(server, "has_extn", None)
                if callable(has_extn):
                    try:
                        supports_starttls = bool(has_extn("starttls"))
                    except Exception:  # pragma: no cover - defensive guard
                        supports_starttls = False
                if supports_starttls:
                    starttls = getattr(server, "starttls", None)
                    if callable(starttls):
                        starttls(context=context)
                        _safe_ehlo(server)
            if settings.user and settings.password:
                server.login(settings.user, settings.password)
            server.send_message(message)

    try:
        _deliver(settings.use_ssl)
        return
    except smtplib.SMTPAuthenticationError:
        logger.error(
            auth_error[0],
            extra=_build_log_extra(
                base=log_extra,
                attempts=attempts,
                action=auth_error[1],
            ),
            exc_info=True,
        )
        return
    except Exception:
        if settings.use_ssl:
            logger.warning(
                ssl_retry[0],
                extra=_build_log_extra(
                    base=log_extra,
                    attempts=attempts,
                    action=ssl_retry[1],
                ),
                exc_info=True,
            )
            try:
                _deliver(False)
                return
            except smtplib.SMTPAuthenticationError:
                logger.error(
                    auth_error[0],
                    extra=_build_log_extra(
                        base=log_extra,
                        attempts=attempts,
                        action=auth_error[1],
                    ),
                    exc_info=True,
                )
                return
            except Exception:
                pass
        logger.error(
            send_failure[0],
            extra=_build_log_extra(
                base=log_extra,
                attempts=attempts,
                action=send_failure[1],
            ),
            exc_info=True,
        )
