"""Unit tests for rate limiters.

`RedisRateLimiter` is tested against **fakeredis** (with its Lua backend via
lupa), so the real Lua window script runs - no external Redis service needed.
"""

import asyncio

import fakeredis
import redis.asyncio as aioredis

from app.domain.ports.rate_limiter import RateLimitDecision
from app.infrastructure.rate_limit.noop_rate_limiter import NoopRateLimiter
from app.infrastructure.rate_limit.redis_rate_limiter import RedisRateLimiter


def make_limiter() -> tuple[RedisRateLimiter, fakeredis.FakeAsyncRedis]:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    return RedisRateLimiter(client=client), client


async def test_allows_within_limit() -> None:
    limiter, _ = make_limiter()
    for _ in range(3):
        decision = await limiter.hit("rl:test:1.2.3.4", limit=3, window_seconds=60)
        assert decision.allowed is True
    await limiter.close()


async def test_rejects_beyond_limit_with_retry_after() -> None:
    limiter, _ = make_limiter()
    for _ in range(3):
        await limiter.hit("k", limit=3, window_seconds=60)
    decision = await limiter.hit("k", limit=3, window_seconds=60)
    assert decision.allowed is False
    assert decision.retry_after >= 1
    await limiter.close()


async def test_keys_are_independent() -> None:
    limiter, _ = make_limiter()
    for _ in range(3):
        await limiter.hit("rl:global:1.1.1.1", limit=3, window_seconds=60)
    # A different scope/IP is not affected.
    assert (await limiter.hit("rl:auth:1.1.1.1", limit=3, window_seconds=60)).allowed
    assert (await limiter.hit("rl:global:2.2.2.2", limit=3, window_seconds=60)).allowed
    await limiter.close()


async def test_window_expires() -> None:
    limiter, _ = make_limiter()
    assert (await limiter.hit("k", limit=1, window_seconds=1)).allowed
    assert (await limiter.hit("k", limit=1, window_seconds=1)).allowed is False
    await asyncio.sleep(1.2)
    assert (await limiter.hit("k", limit=1, window_seconds=1)).allowed
    await limiter.close()


async def test_fail_open_when_backend_unavailable() -> None:
    limiter, _ = make_limiter()

    async def boom(*args: object, **kwargs: object) -> object:
        raise ConnectionError("redis down")

    # Break the script call path entirely.
    limiter._get_client = boom  # type: ignore[method-assign]
    decision: RateLimitDecision = await limiter.hit("k", limit=1, window_seconds=60)
    assert decision.allowed is True  # fail open


async def test_close_with_external_client_does_not_close_it() -> None:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    limiter = RedisRateLimiter(client=client)
    await limiter.hit("k", limit=1, window_seconds=60)
    await limiter.close()
    # The externally provided client must stay usable.
    await client.get("k")


async def test_noop_limiter_allows_everything() -> None:
    limiter = NoopRateLimiter()
    for _ in range(10_000):
        assert (await limiter.hit("k", limit=1, window_seconds=1)).allowed
    await limiter.close()


async def test_type_compatibility() -> None:
    """Both implementations satisfy the RateLimiter protocol."""
    from app.domain.ports.rate_limiter import RateLimiter

    limiter: RateLimiter = make_limiter()[0]
    assert isinstance(limiter, RateLimiter)
    noop: RateLimiter = NoopRateLimiter()
    assert isinstance(noop, RateLimiter)
    _ = aioredis  # keep import used for clarity of the async client type
