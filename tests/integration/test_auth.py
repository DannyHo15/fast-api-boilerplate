"""Integration tests: register / login / me."""

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
