import os
import asyncio
import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse


class RateLimiter:
    """Simple in-memory rate limiter for requests."""

    def __init__(self, limit: int, period: int) -> None:
        self.limit = limit
        self.period = period
        self.history: dict[str, deque] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
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
                return False
            q.append(now)
        return True


AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "100"))
GENERAL_RATE_LIMIT = int(os.getenv("GENERAL_RATE_LIMIT", "1000"))
RATE_PERIOD = int(os.getenv("RATE_PERIOD", "60"))

auth_limiter = RateLimiter(AUTH_RATE_LIMIT, RATE_PERIOD)
general_limiter = RateLimiter(GENERAL_RATE_LIMIT, RATE_PERIOD)


async def rate_limit(request: Request, call_next):
    """Apply simple rate limiting per client IP, honoring proxy headers."""
    ip = (
        request.headers.get("X-Forwarded-For", request.client.host or "unknown")
        .split(",")[0]
        .strip()
    )
    path = request.url.path
    limiter = auth_limiter if path in {"/token", "/auth/login"} else general_limiter
    if not await limiter.is_allowed(ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too Many Requests"},
        )
    return await call_next(request)
