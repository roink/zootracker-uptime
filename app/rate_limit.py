import os
import asyncio
import time
from collections import defaultdict, deque

from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse

from .utils.network import get_client_ip


class RateLimiter:
    """Simple in-memory rate limiter for requests."""

    def __init__(self, limit: int, period: int) -> None:
        self.limit = limit
        self.period = period
        self.history: dict[str, deque] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> tuple[bool, int, float]:
        now = time.monotonic()
        cutoff = now - self.period
        async with self.lock:
            q = self.history[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                del self.history[key]
                q = self.history[key]
            if len(q) >= self.limit:
                retry_after = self.period - (now - q[0])
                return False, 0, retry_after
            q.append(now)
            remaining = self.limit - len(q)
        return True, remaining, 0.0


AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "100"))
GENERAL_RATE_LIMIT = int(os.getenv("GENERAL_RATE_LIMIT", "1000"))
RATE_PERIOD = int(os.getenv("RATE_PERIOD", "60"))
CONTACT_RATE_LIMIT = int(os.getenv("CONTACT_RATE_LIMIT", "5"))
VERIFY_ATTEMPT_LIMIT = int(os.getenv("VERIFY_ATTEMPT_LIMIT", "5"))
VERIFY_ATTEMPT_PERIOD = int(os.getenv("VERIFY_ATTEMPT_PERIOD", "300"))
VERIFY_FAILED_LIMIT = int(os.getenv("VERIFY_FAILED_LIMIT", "10"))
VERIFY_FAILED_PERIOD = int(os.getenv("VERIFY_FAILED_PERIOD", "900"))
VERIFY_RESEND_IP_LIMIT = int(os.getenv("VERIFY_RESEND_IP_LIMIT", "5"))
VERIFY_RESEND_IDENTIFIER_LIMIT = int(
    os.getenv("VERIFY_RESEND_IDENTIFIER_LIMIT", str(VERIFY_RESEND_IP_LIMIT))
)
VERIFY_RESEND_PERIOD = int(os.getenv("VERIFY_RESEND_PERIOD", "3600"))

auth_limiter = RateLimiter(AUTH_RATE_LIMIT, RATE_PERIOD)
general_limiter = RateLimiter(GENERAL_RATE_LIMIT, RATE_PERIOD)
contact_limiter = RateLimiter(CONTACT_RATE_LIMIT, RATE_PERIOD)
verify_ip_limiter = RateLimiter(VERIFY_ATTEMPT_LIMIT, VERIFY_ATTEMPT_PERIOD)
verify_identifier_limiter = RateLimiter(VERIFY_ATTEMPT_LIMIT, VERIFY_ATTEMPT_PERIOD)
verify_failed_ip_limiter = RateLimiter(VERIFY_FAILED_LIMIT, VERIFY_FAILED_PERIOD)
verify_failed_identifier_limiter = RateLimiter(VERIFY_FAILED_LIMIT, VERIFY_FAILED_PERIOD)
verify_resend_ip_limiter = RateLimiter(VERIFY_RESEND_IP_LIMIT, VERIFY_RESEND_PERIOD)
verify_resend_identifier_limiter = RateLimiter(VERIFY_RESEND_IDENTIFIER_LIMIT, VERIFY_RESEND_PERIOD)


async def rate_limit(request: Request, call_next):
    """Apply simple rate limiting per client IP, honoring proxy headers."""
    ip = get_client_ip(request)
    path = request.url.path
    limiter = auth_limiter if path.endswith("/auth/login") else general_limiter
    allowed, remaining, retry_after = await limiter.is_allowed(ip)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too Many Requests"},
            headers={
                "Retry-After": str(int(retry_after)),
                "X-RateLimit-Remaining": "0",
            },
        )
    response = await call_next(request)
    if "X-RateLimit-Remaining" not in response.headers:
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


async def enforce_contact_rate_limit(request: Request) -> None:
    """Limit contact form submissions per client IP."""
    ip = get_client_ip(request)
    allowed, remaining, retry_after = await contact_limiter.is_allowed(ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests",
            headers={
                "Retry-After": str(int(retry_after)),
                "X-RateLimit-Remaining": "0",
            },
        )
    request.state.rate_limit_remaining = remaining


async def enforce_verify_rate_limit(
    request: Request,
    *,
    identifier: str | None = None,
) -> None:
    """Throttle verification attempts per client IP and identifier."""

    ip = get_client_ip(request)
    ip_key = ip or "unknown"
    allowed_ip, ip_remaining, ip_retry_after = await verify_ip_limiter.is_allowed(ip_key)
    if not allowed_ip:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests",
            headers={
                "Retry-After": str(int(ip_retry_after)),
                "X-RateLimit-Remaining": "0",
            },
        )

    remaining = ip_remaining
    if identifier:
        key = identifier.strip().lower()
        allowed_user, user_remaining, user_retry_after = await verify_identifier_limiter.is_allowed(
            key
        )
        if not allowed_user:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests",
                headers={
                    "Retry-After": str(int(user_retry_after)),
                    "X-RateLimit-Remaining": "0",
                },
            )
        remaining = min(remaining, user_remaining)

    request.state.rate_limit_remaining = remaining


async def register_failed_verification_attempt(
    request: Request,
    *,
    identifier: str | None = None,
) -> None:
    """Record a failed verification attempt and raise if the limit is exceeded."""

    ip = get_client_ip(request)
    ip_key = ip or "unknown"
    allowed_ip, _remaining, retry_after = await verify_failed_ip_limiter.is_allowed(ip_key)
    if not allowed_ip:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests",
            headers={
                "Retry-After": str(int(retry_after)),
                "X-RateLimit-Remaining": "0",
            },
        )

    if identifier:
        key = identifier.strip().lower()
        allowed_id, _id_remaining, retry_after = await verify_failed_identifier_limiter.is_allowed(key)
        if not allowed_id:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests",
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Remaining": "0",
                },
            )


async def enforce_verification_resend_limit(
    request: Request,
    identifier: str | None = None,
) -> None:
    """Limit anonymous resend requests per client IP and identifier."""

    ip = get_client_ip(request)
    ip_key = ip or "unknown"
    allowed_ip, ip_remaining, ip_retry_after = await verify_resend_ip_limiter.is_allowed(ip_key)
    if not allowed_ip:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests",
            headers={
                "Retry-After": str(int(ip_retry_after)),
                "X-RateLimit-Remaining": "0",
            },
        )

    remaining = ip_remaining
    if identifier:
        key = identifier.strip().lower()
        allowed_identifier, id_remaining, id_retry_after = await verify_resend_identifier_limiter.is_allowed(key)
        if not allowed_identifier:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too Many Requests",
                headers={
                    "Retry-After": str(int(id_retry_after)),
                    "X-RateLimit-Remaining": "0",
                },
            )
        remaining = min(remaining, id_remaining)

    request.state.rate_limit_remaining = remaining
