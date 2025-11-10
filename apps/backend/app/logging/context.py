"""Request scoped context helpers for logging."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from .ip_utils import anonymize_ip

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx_var: ContextVar[str | None] = ContextVar("user_id", default=None)
client_ip_ctx_var: ContextVar[str | None] = ContextVar("client_ip", default=None)
client_ip_raw_ctx_var: ContextVar[str | None] = ContextVar("client_ip_raw", default=None)
client_ip_anonymized_ctx_var: ContextVar[str | None] = ContextVar(
    "client_ip_anonymized", default=None
)


@dataclass
class RequestContextTokens:
    """Container storing tokens for context variables set per request."""

    request_id_token: Token[str | None]
    user_id_token: Token[str | None]
    client_ip_token: Token[str | None]
    client_ip_raw_token: Token[str | None]
    client_ip_anonymized_token: Token[str | None]


def bind_request_context(
    request_id: str,
    client_ip: str | None = None,
    *,
    client_ip_raw: str | None = None,
    client_ip_anonymized: str | None = None,
) -> RequestContextTokens:
    """Bind request level context values and return the created tokens."""

    if client_ip_raw is None:
        client_ip_raw = client_ip
    if client_ip_anonymized is None and client_ip_raw:
        client_ip_anonymized = anonymize_ip(client_ip_raw, mode="anonymized")

    return RequestContextTokens(
        request_id_ctx_var.set(request_id),
        user_id_ctx_var.set(None),
        client_ip_ctx_var.set(client_ip),
        client_ip_raw_ctx_var.set(client_ip_raw),
        client_ip_anonymized_ctx_var.set(client_ip_anonymized),
    )


def reset_request_context(tokens: RequestContextTokens) -> None:
    """Reset request scoped context variables using the provided tokens."""

    request_id_ctx_var.reset(tokens.request_id_token)
    user_id_ctx_var.reset(tokens.user_id_token)
    client_ip_ctx_var.reset(tokens.client_ip_token)
    client_ip_raw_ctx_var.reset(tokens.client_ip_raw_token)
    client_ip_anonymized_ctx_var.reset(tokens.client_ip_anonymized_token)


def set_user_context(user_id: str | None) -> None:
    """Store the current user id in the context for downstream log records."""

    user_id_ctx_var.set(user_id)
