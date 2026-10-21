"""Application settings loaded from environment variables / `.env` file.

Usage:
    from app.core.config import get_settings

    settings = get_settings()
    print(settings.database_url)
"""

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Typed application settings.

    Every field can be overridden with an environment variable of the same
    name (case-insensitive), e.g. `DATABASE_URL`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "FastAPI Boilerplate"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    # SQLite by default (zero-setup for local dev);
    # use e.g. postgresql+asyncpg://user:pass@host:5432/db in production.
    database_url: str = "sqlite+aiosqlite:///./app.db"
    # Dev convenience: create tables automatically on startup.
    # Keep `false` in production and use `alembic upgrade head` instead.
    auto_create_tables: bool = False

    # Security
    # HS256 signing key, at least 32 characters (`openssl rand -hex 32`).
    # The app refuses to start with a shorter key unless DEBUG=true.
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Rate limiting (Redis-backed, fixed window, per client IP)
    # Empty REDIS_URL => rate limiting is disabled (NoopRateLimiter).
    # Behind a reverse proxy, set uvicorn's FORWARDED_ALLOW_IPS so the client
    # IP comes from X-Forwarded-For instead of the proxy's address.
    redis_url: str = ""
    rate_limit_enabled: bool = True
    # Global limit applied to every v1 endpoint except health (per IP per window).
    rate_limit_global: int = 100
    rate_limit_window_seconds: int = 60
    # Stricter limit for /auth/register and /auth/login (per IP per minute).
    rate_limit_auth_per_minute: int = 10

    # CORS - a JSON list, e.g. ["https://app.example.com"]
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    def check_secret_key(self) -> None:
        """Refuse a weak JWT signing key outside debug mode."""
        if len(self.secret_key) >= MIN_SECRET_KEY_LENGTH:
            return
        if not self.debug:
            raise RuntimeError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters "
                "(run `make env`, or `openssl rand -hex 32`), or set DEBUG=true for local dev."
            )
        logger.warning("Weak SECRET_KEY accepted because DEBUG=true - never deploy like this")


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (create once, reuse everywhere)."""
    return Settings()
