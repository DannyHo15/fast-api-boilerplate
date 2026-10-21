"""Small helpers for the integration tests."""

from typing import Any

from httpx import AsyncClient

DEFAULT_EMAIL = "alice@example.com"
DEFAULT_PASSWORD = "supersecret1"


async def register_and_login(
    client: AsyncClient,
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    full_name: str | None = None,
) -> dict[str, Any]:
    """Register a user, log in, and return the token response body."""
    payload: dict[str, Any] = {"email": email, "password": password}
    if full_name is not None:
        payload["full_name"] = full_name

    response = await client.post("/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    response = await client.post("/v1/auth/login", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
