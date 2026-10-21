"""SQLAlchemy implementation of `app.domain.ports.user_repository.UserRepository`."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.infrastructure.database.mappers import user_to_domain
from app.infrastructure.database.models.user import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
            created_at=user.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return user_to_domain(model)

    async def get(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return user_to_domain(model) if model is not None else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return user_to_domain(model) if model is not None else None
