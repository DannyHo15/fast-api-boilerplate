"""FastAPI dependencies: sessions (unit of work), repositories, services,
and the authenticated current user.

This is the composition root for HTTP requests - the only place where the
domain ports are wired to their infrastructure implementations.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError
from app.domain.entities.user import User
from app.domain.exceptions import InvalidCredentialsError, RateLimitedError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.rate_limiter import RateLimiter
from app.domain.ports.token_service import TokenService
from app.infrastructure.database.session import Database
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

_settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{_settings.api_v1_prefix}/auth/login")


def get_database(request: Request) -> Database:
    return request.app.state.database  # type: ignore[no-any-return]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request = one transaction (unit of work).

    Commits on success, rolls back on any exception, then closes.
    """
    database: Database = request.app.state.database
    async with database.session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


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


def rate_limit(scope: str, *, limit: int, window_seconds: int) -> Callable[..., Awaitable[None]]:
    """Build a FastAPI dependency enforcing `limit` hits per `window_seconds`.

    The counter is keyed per client IP within `scope` (namespaced keys, so
    e.g. the strict "auth" budget does not consume the "global" budget).

    Usage:
        @router.post("/login",
                     dependencies=[Depends(rate_limit("auth", limit=10, window_seconds=60))])
    """

    async def _enforce(
        request: Request,
        limiter: RateLimiterDep,
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        decision = await limiter.hit(f"rl:{scope}:{client_ip}", limit, window_seconds)
        if not decision.allowed:
            raise RateLimitedError(retry_after=decision.retry_after)

    return _enforce


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
