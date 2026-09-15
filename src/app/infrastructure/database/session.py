"""Async engine / session management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Owns the engine and hands out sessions.

    One request = one session = one transaction (unit of work).
    The API layer commits/rolls back the session around the request
    (see `app.api.deps.get_session`).
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self._engine.dispose()


def create_database(database_url: str) -> Database:
    """Create a `Database` for the given SQLAlchemy URL.

    Example URLs:
        sqlite+aiosqlite:///./app.db
        postgresql+asyncpg://user:pass@host:5432/dbname
    """
    is_sqlite = database_url.startswith("sqlite")
    engine = create_async_engine(
        database_url,
        echo=False,
        # SQLite: a single connection avoids "database is locked" issues.
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    return Database(engine)
