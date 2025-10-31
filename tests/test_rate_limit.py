from app import rate_limit
from app.rate_limit import RateLimiter


import asyncio


async def test_rate_limit_respects_forwarded_for_header(client, monkeypatch):
    """Rate limiter should honor X-Forwarded-For for client IPs."""
    monkeypatch.setattr(rate_limit, "general_limiter", RateLimiter(1, 60))

    resp1 = await client.get("/zoos", headers={"X-Forwarded-For": "1.1.1.1"})
    assert resp1.status_code == 200

    resp2 = await client.get("/zoos", headers={"X-Forwarded-For": "1.1.1.1"})
    assert resp2.status_code == 429

    resp3 = await client.get("/zoos", headers={"X-Forwarded-For": "2.2.2.2"})
    assert resp3.status_code == 200


async def test_rate_limiter_hit_and_miss(client):
    """First request allowed, second blocked for same IP."""
    limiter = RateLimiter(1, 60)

    async def run_checks():
        allowed, _, _ = await limiter.is_allowed("1.1.1.1")
        assert allowed
        allowed, _, _ = await limiter.is_allowed("1.1.1.1")
        assert not allowed

    asyncio.run(run_checks())

