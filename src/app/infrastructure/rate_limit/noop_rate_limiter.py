"""Rate limiter that allows everything (limiter disabled / no Redis configured)."""

from app.domain.ports.rate_limiter import RateLimitDecision


class NoopRateLimiter:
    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        return RateLimitDecision(allowed=True)

    async def close(self) -> None:
        pass
