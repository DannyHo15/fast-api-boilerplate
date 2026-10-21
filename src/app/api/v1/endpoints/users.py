"""User profile endpoints."""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.api.schemas.user import UserRead
from app.domain.entities.user import User

router = APIRouter()


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the authenticated user's profile",
)
async def read_me(user: CurrentUser) -> User:
    return user
