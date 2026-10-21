"""Integration tests: health endpoints and startup checks."""

import pytest


async def test_root_liveness(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_v1_readiness_checks_database(client) -> None:
    response = await client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.parametrize(
    ("secret_key", "debug", "ok"),
    [("short", False, False), ("short", True, True), ("x" * 32, False, True)],
)
async def test_startup_refuses_weak_secret_key_outside_debug(
    tmp_path, secret_key: str, debug: bool, ok: bool
) -> None:
    from app.core.config import Settings
    from app.main import create_app, lifespan

    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/s.db",
            secret_key=secret_key,
            debug=debug,
        )
    )
    if ok:
        async with lifespan(app):
            pass
    else:
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            async with lifespan(app):
                pass
