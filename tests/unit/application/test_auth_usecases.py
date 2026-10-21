"""Unit tests for auth use cases."""

import pytest

from app.application.auth.authenticate import AuthenticateUserInput, AuthenticateUserUseCase
from app.application.auth.register import RegisterUserInput, RegisterUserUseCase
from app.domain.exceptions import ConflictError, DomainError, InvalidCredentialsError
from tests.unit.application.fakes import (
    FakePasswordHasher,
    InMemoryUserRepository,
)


async def test_register_normalizes_email_and_hashes_password() -> None:
    repo = InMemoryUserRepository()
    usecase = RegisterUserUseCase(repo, FakePasswordHasher())

    user = await usecase.execute(
        RegisterUserInput(
            email="  Alice@Example.com ",
            password="supersecret1",
            full_name="  Alice ",
        )
    )

    assert user.email == "alice@example.com"
    assert user.password_hash == "hashed:supersecret1"
    assert user.full_name == "Alice"
    assert await repo.get_by_email("alice@example.com") is not None


async def test_register_rejects_duplicate_email() -> None:
    repo = InMemoryUserRepository()
    usecase = RegisterUserUseCase(repo, FakePasswordHasher())

    await usecase.execute(RegisterUserInput(email="alice@example.com", password="supersecret1"))
    with pytest.raises(ConflictError):
        await usecase.execute(RegisterUserInput(email="ALICE@example.com", password="othersecret1"))


# 73 ASCII bytes, and 25 x 3-byte chars = 75 bytes: both over bcrypt's 72-byte limit.
@pytest.mark.parametrize("password", ["short", "x" * 73, "ặ" * 25])
async def test_register_rejects_invalid_password(password: str) -> None:
    usecase = RegisterUserUseCase(InMemoryUserRepository(), FakePasswordHasher())
    with pytest.raises(DomainError):
        await usecase.execute(RegisterUserInput(email="alice@example.com", password=password))


async def test_authenticate_success() -> None:
    repo = InMemoryUserRepository()
    usecase = AuthenticateUserUseCase(repo, FakePasswordHasher())
    await RegisterUserUseCase(repo, FakePasswordHasher()).execute(
        RegisterUserInput(email="alice@example.com", password="supersecret1")
    )

    user = await usecase.execute(
        AuthenticateUserInput(email="alice@example.com", password="supersecret1")
    )
    assert user.email == "alice@example.com"


@pytest.mark.parametrize(
    "email, password",
    [
        ("ghost@example.com", "supersecret1"),  # unknown email
        ("alice@example.com", "wrongpassword"),  # wrong password
    ],
)
async def test_authenticate_failure(email: str, password: str) -> None:
    repo = InMemoryUserRepository()
    usecase = AuthenticateUserUseCase(repo, FakePasswordHasher())
    await RegisterUserUseCase(repo, FakePasswordHasher()).execute(
        RegisterUserInput(email="alice@example.com", password="supersecret1")
    )

    with pytest.raises(InvalidCredentialsError):
        await usecase.execute(AuthenticateUserInput(email=email, password=password))


async def test_authenticate_unknown_email_still_spends_a_hash() -> None:
    """Unknown email costs one bcrypt round too, so timing does not reveal it."""

    class CountingHasher(FakePasswordHasher):
        calls = 0

        def hash(self, password: str) -> str:
            self.calls += 1
            return super().hash(password)

    hasher = CountingHasher()
    usecase = AuthenticateUserUseCase(InMemoryUserRepository(), hasher)
    with pytest.raises(InvalidCredentialsError):
        await usecase.execute(AuthenticateUserInput(email="ghost@example.com", password="x" * 8))
    assert hasher.calls == 1
