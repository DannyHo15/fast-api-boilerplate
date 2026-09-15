"""User entity and its business rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.domain.exceptions import DomainError

MAX_EMAIL_LENGTH = 255
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_FULL_NAME_LENGTH = 255


def normalize_email(email: str) -> str:
    """Validate and normalize an email address (lowercase, trimmed)."""
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized or normalized.count("@") != 1:
        raise DomainError("A valid email address is required")
    if len(normalized) > MAX_EMAIL_LENGTH:
        raise DomainError(f"Email must be at most {MAX_EMAIL_LENGTH} characters")
    return normalized


def validate_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise DomainError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise DomainError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")
    return password


@dataclass
class User:
    id: UUID
    email: str
    password_hash: str
    full_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
