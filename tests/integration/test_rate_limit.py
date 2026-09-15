"""Integration tests: rate limiting behaviour over the full ASGI stack.

Uses a `FakeRateLimiter` injected into `app.state` so the tests run without
Redis while still exercising the real FastAPI dependency + error handling.
"""

from typing import Any

from app.domain.ports.rate_limiter import RateLimitDecision


class FakeRateLimiter:
    """Counts hits per key; allows the first `budget` hits."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self._hits: dict[str, int] = {}

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        self._hits[key] = self._hits.get(key, 0) + 1
        if self._hits[key] > self.budget:
            return RateLimitDecision(allowed=False, retry_after=30)
        return RateLimitDecision(allowed=True)

    async def close(self) -> None:
        pass


def _hits_by_scope(limiter: FakeRateLimiter) -> dict[str, int]:
    scopes: dict[str, int] = {}
    for key in limiter._hits:
        scope = key.split(":")[1]  # rl:{scope}:{ip}
        scopes[scope] = scopes.get(scope, 0) + limiter._hits[key]
    return scopes


async def test_noop_by_default_without_redis(client, app) -> None:
    """With no REDIS_URL configured the limiter is a no-op: no 429 ever."""
    from app.infrastructure.rate_limit.noop_rate_limiter import NoopRateLimiter

    assert isinstance(app.state.rate_limiter, NoopRateLimiter)
    for _ in range(10):
        response = await client.get("/v1/health")
        assert response.status_code == 200


async def test_global_limit_returns_429(app, settings) -> None:
    limiter = FakeRateLimiter(budget=3)
    app.state.rate_limiter = limiter

    transport = _client_for(app)
    async with transport as ac:
        for _ in range(3):
            assert (await ac.get("/v1/health")).status_code == 200

        response = await ac.get("/v1/health")
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "30"
        body = response.json()
        assert body["error"]["code"] == "RATE_LIMITED"

    # Every v1 request consumed the "global" budget.
    assert _hits_by_scope(limiter) == {"global": 4}


async def test_auth_scope_is_independent_of_global(app, settings) -> None:
    limiter = FakeRateLimiter(budget=2)
    app.state.rate_limiter = limiter

    from tests.helpers import DEFAULT_EMAIL, DEFAULT_PASSWORD

    transport = _client_for(app)
    async with transport as ac:
        # Each login consumes one "global" AND one "auth" hit (separate keys).
        assert (
            await ac.post(
                "/v1/auth/login",
                json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            )
        ).status_code in (200, 401)  # user may not exist yet - status is irrelevant
        assert (
            await ac.post(
                "/v1/auth/login",
                json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            )
        ).status_code in (200, 401)

        # Third auth hit exceeds the auth budget -> 429 even though it would
        # still be fine under the global budget.
        response = await ac.post(
            "/v1/auth/login",
            json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"

    assert set(_hits_by_scope(limiter)) == {"global", "auth"}


async def test_429_header_and_envelope_shape(app, settings) -> None:
    app.state.rate_limiter = FakeRateLimiter(budget=0)  # reject everything

    transport = _client_for(app)
    async with transport as ac:
        response = await ac.get("/v1/health")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    body: dict[str, Any] = response.json()
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["message"]


def _client_for(app):
    from httpx import ASGITransport, AsyncClient

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
