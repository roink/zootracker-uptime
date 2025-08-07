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

auth_limiter = RateLimiter(AUTH_RATE_LIMIT, RATE_PERIOD)
general_limiter = RateLimiter(GENERAL_RATE_LIMIT, RATE_PERIOD)
contact_limiter = RateLimiter(CONTACT_RATE_LIMIT, RATE_PERIOD)


async def rate_limit(request: Request, call_next):
    """Apply simple rate limiting per client IP, honoring proxy headers."""
    ip = get_client_ip(request)
    path = request.url.path
    limiter = auth_limiter if path in {"/token", "/auth/login"} else general_limiter
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
