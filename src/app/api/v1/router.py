"""Aggregates all v1 routers under the API prefix.

The router-level dependency applies the GLOBAL rate limit to every v1
endpoint (per client IP). Individual endpoints can add stricter,
scope-specific limits on top (see `auth.py`).
"""

from fastapi import APIRouter, Depends

from app.api.deps import rate_limit
from app.api.v1.endpoints import auth, health, tasks, users
from app.core.config import get_settings

_settings = get_settings()

api_router = APIRouter(
    dependencies=[
        Depends(
            rate_limit(
                "global",
                limit=_settings.rate_limit_global,
                window_seconds=_settings.rate_limit_window_seconds,
            )
        )
    ]
)

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
