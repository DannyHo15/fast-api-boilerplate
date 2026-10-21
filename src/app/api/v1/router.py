"""Aggregates all v1 routers under the API prefix.

Every v1 router except health gets the GLOBAL rate limit (per client IP);
health stays unlimited so load-balancer probes never get a 429. Individual
endpoints can add stricter, scope-specific limits on top (see `auth.py`).
"""

from fastapi import APIRouter, Depends

from app.api.deps import rate_limit
from app.api.v1.endpoints import auth, health, tasks, users

rate_limited = [
    Depends(
        rate_limit(
            "global",
            limit=lambda s: s.rate_limit_global,
            window_seconds=lambda s: s.rate_limit_window_seconds,
        )
    )
]

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"], dependencies=rate_limited)
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=rate_limited)
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"], dependencies=rate_limited)
