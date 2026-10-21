"""Use case: register a new user account."""

from dataclasses import dataclass
from uuid import uuid4

from app.domain.entities.user import (
    User,
    normalize_email,
    validate_password,
)
from app.domain.exceptions import ConflictError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class RegisterUserInput:
    email: str
    password: str
    full_name: str | None = None


class RegisterUserUseCase:
    def __init__(self, users: UserRepository, passwords: PasswordHasher) -> None:
        self._users = users
        self._passwords = passwords

    async def execute(self, input: RegisterUserInput) -> User:
        email = normalize_email(input.email)
        validate_password(input.password)

        if await self._users.get_by_email(email) is not None:
            raise ConflictError(f"Email {email} is already registered")

        full_name = input.full_name.strip() if input.full_name else None
        user = User(
            id=uuid4(),
            email=email,
            password_hash=self._passwords.hash(input.password),
            full_name=full_name or None,
        )
        return await self._users.add(user)
