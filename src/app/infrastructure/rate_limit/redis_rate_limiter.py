"""Redis implementation of `app.domain.ports.rate_limiter.RateLimiter`.

Fixed-window counter using a single atomic Lua script (INCR + EXPIRE + TTL),
so the window cannot leak a key without expiry even if a worker dies mid-call.
Fails OPEN when Redis is unreachable (a broken limiter must not take the
API down) and logs the error.
"""

import logging

import redis.asyncio as aioredis

from app.domain.ports.rate_limiter import RateLimitDecision

logger = logging.getLogger(__name__)

# KEYS[1] = counter key, ARGV[1] = limit, ARGV[2] = window (seconds)
# Returns {current_count, ttl_seconds}
_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
    ttl = tonumber(ARGV[2])
end
return {current, ttl}
"""


class RedisRateLimiter:
    def __init__(self, redis_url: str = "", *, client: aioredis.Redis | None = None) -> None:
        """`client` is injectable for tests (e.g. fakeredis)."""
        self._redis_url = redis_url
        self._external_client = client
        self._client: aioredis.Redis | None = client

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        try:
            client = await self._get_client()
            script = client.register_script(_WINDOW_SCRIPT)
            current, ttl = await script(keys=[key], args=[limit, window_seconds])
        except Exception:
            logger.exception("Rate limiter backend unavailable (key=%s) - failing open", key)
            return RateLimitDecision(allowed=True)

        current = int(current)
        ttl = max(int(ttl), 0)
        if current <= limit:
            return RateLimitDecision(allowed=True)
        return RateLimitDecision(allowed=False, retry_after=max(ttl, 1))

    async def close(self) -> None:
        if self._client is not None and self._external_client is None:
            await self._client.aclose()
        self._client = None
