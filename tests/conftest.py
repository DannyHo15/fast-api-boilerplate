"""Shared fixtures: a fully wired app against a throwaway SQLite database."""

import pytest
from httpx import ASGITransport, AsyncClient

import app.infrastructure.database.models  # register ORM models on Base.metadata
from app.core.config import Settings
from app.infrastructure.database import Base, create_database
from app.main import create_app


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        app_name="Test App",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        auto_create_tables=False,
        secret_key="test-secret-key-0123456789-01234567890123",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        cors_origins=["*"],
        default_page_size=20,
        max_page_size=100,
    )


@pytest.fixture()
async def app(settings: Settings):
    application = create_app(settings)
    database = create_database(settings.database_url)
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application.state.database = database
    try:
        yield application
    finally:
        await database.dispose()


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
