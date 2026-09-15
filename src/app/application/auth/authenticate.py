"""Use case: authenticate a user and (later) issue a token for them."""

from dataclasses import dataclass

from app.domain.entities.user import User, normalize_email
from app.domain.exceptions import InvalidCredentialsError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class AuthenticateUserInput:
    email: str
    password: str


class AuthenticateUserUseCase:
    def __init__(self, users: UserRepository, passwords: PasswordHasher) -> None:
        self._users = users
        self._passwords = passwords

    async def execute(self, input: AuthenticateUserInput) -> User:
        user = await self._users.get_by_email(normalize_email(input.email))
        # Deliberately the same error for unknown email and wrong password:
        # do not leak which emails exist.
        if user is None or not self._passwords.verify(input.password, user.password_hash):
            raise InvalidCredentialsError("Incorrect email or password")
        return user
