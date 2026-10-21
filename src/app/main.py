"""Application entry point (FastAPI adapter).

Run locally:
    uvicorn app.main:app --reload

The `create_app` factory makes the app easy to instantiate in tests with
custom settings.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.infrastructure.database import Base, create_database
from app.infrastructure.database import models as _models  # noqa: F401 (registers ORM models)
from app.infrastructure.rate_limit import build_rate_limiter
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_token_service import JwtTokenService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create/destroy application resources around the app's lifetime."""
    settings: Settings = app.state.settings
    database = create_database(settings.database_url)
    if settings.auto_create_tables:
        async with database.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables ensured (auto_create_tables=true)")
    app.state.database = database
    try:
        yield
    finally:
        await app.state.rate_limiter.close()
        await database.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )

    # Services shared across requests (stateless, cheap to build once).
    app.state.settings = settings
    app.state.password_hasher = BcryptPasswordHasher()
    app.state.token_service = JwtTokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )
    app.state.rate_limiter = build_rate_limiter(settings)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health", tags=["health"], summary="Liveness check")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app: FastAPI = create_app()
