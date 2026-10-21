"""FastAPI dependencies: sessions (unit of work), repositories, services,
and the authenticated current user.

This is the composition root for HTTP requests - the only place where the
domain ports are wired to their infrastructure implementations.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import API_V1_PREFIX
from app.core.config import Settings
from app.core.exceptions import InvalidTokenError
from app.domain.entities.user import User
from app.domain.exceptions import InvalidCredentialsError, RateLimitedError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.rate_limiter import RateLimiter
from app.domain.ports.token_service import TokenService
from app.infrastructure.database.session import Database
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_PREFIX}/auth/login")


def get_database(request: Request) -> Database:
    return request.app.state.database  # type: ignore[no-any-return]


def get_settings_dep(request: Request) -> Settings:
    """The `Settings` the app was created with (not the global env settings)."""
    return request.app.state.settings  # type: ignore[no-any-return]


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request = one transaction (unit of work).

    Commits on success, rolls back on any exception, then closes.
    `scope="function"` (below) makes this run before the response is sent,
    so a failed commit becomes a 500 instead of a silently lost write.
    """
    database: Database = request.app.state.database
    async with database.session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_user_repository(session: SessionDep) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


UserRepositoryDep = Annotated[SqlAlchemyUserRepository, Depends(get_user_repository)]


def get_task_repository(session: SessionDep) -> SqlAlchemyTaskRepository:
    return SqlAlchemyTaskRepository(session)


TaskRepositoryDep = Annotated[SqlAlchemyTaskRepository, Depends(get_task_repository)]


def get_password_hasher(request: Request) -> PasswordHasher:
    return request.app.state.password_hasher  # type: ignore[no-any-return]


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service  # type: ignore[no-any-return]


TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter  # type: ignore[no-any-return]


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def rate_limit(
    scope: str,
    *,
    limit: int | Callable[[Settings], int],
    window_seconds: int | Callable[[Settings], int],
) -> Callable[..., Awaitable[None]]:
    """Build a FastAPI dependency enforcing `limit` hits per `window_seconds`.

    The counter is keyed per client IP within `scope` (namespaced keys, so
    e.g. the strict "auth" budget does not consume the "global" budget).
    `limit` / `window_seconds` can be callables reading the app's settings
    at request time.

    Usage:
        @router.post("/export",
                     dependencies=[Depends(rate_limit("export", limit=5, window_seconds=3600))])
        rate_limit("global", limit=lambda s: s.rate_limit_global, window_seconds=60)
    """

    async def _enforce(
        request: Request,
        limiter: RateLimiterDep,
        settings: SettingsDep,
    ) -> None:
        # Behind a proxy this is the real client IP only if uvicorn trusts the
        # proxy (FORWARDED_ALLOW_IPS) - otherwise every client shares one bucket.
        client_ip = request.client.host if request.client else "unknown"
        max_hits = limit(settings) if callable(limit) else limit
        window = window_seconds(settings) if callable(window_seconds) else window_seconds
        decision = await limiter.hit(f"rl:{scope}:{client_ip}", max_hits, window)
        if not decision.allowed:
            raise RateLimitedError(retry_after=decision.retry_after)

    return _enforce


@dataclass(frozen=True, slots=True)
class PageParams:
    offset: int
    limit: int


def get_page_params(
    settings: SettingsDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[
        int | None, Query(ge=1, description="Page size (default/max: DEFAULT/MAX_PAGE_SIZE)")
    ] = None,
) -> PageParams:
    """`offset` / `limit` query params, bounded by the app's page-size settings."""
    if limit is None:
        return PageParams(offset=offset, limit=settings.default_page_size)
    if limit > settings.max_page_size:
        raise RequestValidationError(
            [
                {
                    "type": "less_than_equal",
                    "loc": ("query", "limit"),
                    "msg": f"Input should be less than or equal to {settings.max_page_size}",
                    "input": limit,
                    "ctx": {"le": settings.max_page_size},
                }
            ]
        )
    return PageParams(offset=offset, limit=limit)


PageParamsDep = Annotated[PageParams, Depends(get_page_params)]


async def get_current_user(
    request: Request,
    session: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Resolve the authenticated user from the Bearer token.

    Raises `InvalidCredentialsError` (mapped to 401 by the API layer) for
    missing/invalid/expired tokens or unknown users.
    """
    token_service: TokenService = request.app.state.token_service
    try:
        subject = token_service.decode_access_token(token)
    except InvalidTokenError as exc:
        raise InvalidCredentialsError("Invalid or expired token") from exc

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise InvalidCredentialsError("Invalid token subject") from exc

    user = await SqlAlchemyUserRepository(session).get(user_id)
    if user is None:
        raise InvalidCredentialsError("User no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
