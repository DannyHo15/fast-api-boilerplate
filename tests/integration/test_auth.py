"""Integration tests: register / login / me."""

import pytest

from tests.helpers import DEFAULT_EMAIL, DEFAULT_PASSWORD, auth_headers, register_and_login


async def test_register_returns_user_without_secrets(client) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"email": "bob@example.com", "password": "supersecret1", "full_name": "Bob"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert body["full_name"] == "Bob"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email_returns_409(client) -> None:
    await register_and_login(client)
    response = await client.post(
        "/v1/auth/register",
        json={"email": DEFAULT_EMAIL, "password": "supersecret1"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_register_short_password_returns_422(client) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"email": "bob@example.com", "password": "short"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_register_invalid_email_returns_422(client) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"email": "not-an-email", "password": "supersecret1"},
    )
    assert response.status_code == 422


async def test_login_returns_token_and_user(client) -> None:
    await register_and_login(client)  # ensures the user exists
    response = await client.post(
        "/v1/auth/login",
        json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == DEFAULT_EMAIL


async def test_login_wrong_password_returns_401(client) -> None:
    await register_and_login(client)
    response = await client.post(
        "/v1/auth/login",
        json={"email": DEFAULT_EMAIL, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email_returns_401(client) -> None:
    response = await client.post(
        "/v1/auth/login",
        json={"email": "ghost@example.com", "password": "supersecret1"},
    )
    assert response.status_code == 401


async def test_me_with_token(client) -> None:
    body = await register_and_login(client, full_name="Alice")
    response = await client.get("/v1/users/me", headers=auth_headers(body["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == DEFAULT_EMAIL
    assert response.json()["full_name"] == "Alice"


async def test_me_without_token_returns_401(client) -> None:
    response = await client.get("/v1/users/me")
    assert response.status_code == 401


async def test_me_with_garbage_token_returns_401(client) -> None:
    response = await client.get("/v1/users/me", headers=auth_headers("garbage.token.here"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_register_password_over_72_bytes_is_rejected_not_500(client) -> None:
    # 30 characters passes the schema, but 90 UTF-8 bytes exceeds bcrypt's limit.
    response = await client.post(
        "/v1/auth/register", json={"email": "viet@example.com", "password": "ặ" * 30}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DOMAIN_ERROR"

    response = await client.post(
        "/v1/auth/register", json={"email": "long@example.com", "password": "x" * 80}
    )
    assert response.status_code == 422


async def test_401_responses_carry_www_authenticate(client) -> None:
    for headers in ({}, {"Authorization": "Bearer garbage"}):
        response = await client.get("/v1/users/me", headers=headers)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    response = await client.post(
        "/v1/auth/login", json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_405_keeps_allow_header(client) -> None:
    response = await client.put("/v1/tasks")
    assert response.status_code == 405
    assert response.headers["Allow"]


async def test_concurrent_duplicate_email_is_a_conflict(app) -> None:
    """The unique index, not only the pre-check, turns a duplicate into 409."""
    from app.domain.exceptions import ConflictError
    from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
    from tests.unit.application.fakes import make_user

    async with app.state.database.session() as session:
        repo = SqlAlchemyUserRepository(session)
        await repo.add(make_user(email="race@example.com"))
        with pytest.raises(ConflictError):
            await repo.add(make_user(email="race@example.com"))


async def test_failed_commit_returns_500_and_persists_nothing(app, monkeypatch) -> None:
    """The commit happens before the response, so its failure reaches the client."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.database.models import UserModel

    async def failing_commit(self: AsyncSession) -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.post(
            "/v1/auth/register", json={"email": "lost@example.com", "password": "x" * 8}
        )
    assert response.status_code == 500
    monkeypatch.undo()

    async with app.state.database.session() as session:
        count = (await session.execute(select(func.count()).select_from(UserModel))).scalar_one()
    assert count == 0
