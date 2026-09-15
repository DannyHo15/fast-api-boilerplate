"""Rate limiting infrastructure.

`build_rate_limiter` picks the implementation based on settings:
- Redis configured  -> `RedisRateLimiter` (shared state, works across workers)
- otherwise         -> `NoopRateLimiter` (allows everything - zero-setup dev)
"""

import logging

from app.core.config import Settings
from app.domain.ports.rate_limiter import RateLimiter
from app.infrastructure.rate_limit.noop_rate_limiter import NoopRateLimiter
from app.infrastructure.rate_limit.redis_rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

__all__ = ["NoopRateLimiter", "RedisRateLimiter", "build_rate_limiter"]


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if not settings.rate_limit_enabled or not settings.redis_url:
        logger.info(
            "Rate limiting disabled (rate_limit_enabled=%s, redis_url=%r) "
            "- all requests are allowed",
            settings.rate_limit_enabled,
            settings.redis_url,
        )
        return NoopRateLimiter()
    return RedisRateLimiter(settings.redis_url)
