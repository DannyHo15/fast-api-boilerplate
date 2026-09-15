"""Auth endpoints: register and login."""

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    PasswordHasherDep,
    TokenServiceDep,
    UserRepositoryDep,
    rate_limit,
)
from app.api.schemas.auth import LoginRequest, TokenResponse
from app.api.schemas.user import UserCreate, UserRead
from app.application.auth.authenticate import AuthenticateUserInput, AuthenticateUserUseCase
from app.application.auth.register import RegisterUserInput, RegisterUserUseCase
from app.domain.entities.user import User

router = APIRouter()

# Stricter budget for auth endpoints (per IP per minute) to slow down
# brute-force / credential-stuffing attempts. Stacked on top of the global
# limit, keyed in its own "auth" scope.
AUTH_LIMIT_PER_MINUTE = 10
auth_rate_limit = [Depends(rate_limit("auth", limit=AUTH_LIMIT_PER_MINUTE, window_seconds=60))]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    dependencies=auth_rate_limit,
)
async def register(
    payload: UserCreate,
    users: UserRepositoryDep,
    passwords: PasswordHasherDep,
) -> User:
    """Create a new user. The password is stored as a bcrypt hash only."""
    usecase = RegisterUserUseCase(users, passwords)
    return await usecase.execute(
        RegisterUserInput(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT",
    dependencies=auth_rate_limit,
)
async def login(
    payload: LoginRequest,
    users: UserRepositoryDep,
    passwords: PasswordHasherDep,
    tokens: TokenServiceDep,
) -> TokenResponse:
    """Exchange email + password for a Bearer token (subject = user id)."""
    user = await AuthenticateUserUseCase(users, passwords).execute(
        AuthenticateUserInput(email=payload.email, password=payload.password)
    )
    access_token = tokens.create_access_token(subject=str(user.id))
    return TokenResponse(
        access_token=access_token,
        user=UserRead.model_validate(user),
    )
