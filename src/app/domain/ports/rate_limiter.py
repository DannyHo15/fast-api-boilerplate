"""Port for rate limiting."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of a rate-limit check.

    `retry_after` (seconds until the window resets) is meaningful when
    `allowed` is False.
    """

    allowed: bool
    retry_after: int = 0


@runtime_checkable
class RateLimiter(Protocol):
    """Fixed-window rate limiter.

    Implementations must be safe for concurrent use and must **fail open**
    (allow the request) when the backend is unavailable - a broken limiter
    should not take the API down.
    """

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        """Count one hit for `key` and return the decision."""
        ...

    async def close(self) -> None:
        """Release any resources (called at application shutdown)."""
        ...
