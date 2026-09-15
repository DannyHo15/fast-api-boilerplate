"""In-memory fakes implementing the domain ports.

Because the ports are `typing.Protocol`s, these fakes need no base class -
structural typing does the rest.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.domain.entities.task import Task, TaskStatus
from app.domain.entities.user import User


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    async def add(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    async def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    async def get_owned(self, task_id: UUID, owner_id: UUID) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None or task.owner_id != owner_id:
            return None
        return task

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        status: TaskStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        items = [t for t in self._tasks.values() if t.owner_id == owner_id]
        if status is not None:
            items = [t for t in items if t.status is status]
        items.sort(key=lambda t: (t.created_at, t.id), reverse=True)
        return items[offset : offset + limit], len(items)

    async def save(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    async def delete(self, task_id: UUID, owner_id: UUID) -> bool:
        task = self._tasks.get(task_id)
        if task is None or task.owner_id != owner_id:
            return False
        del self._tasks[task_id]
        return True


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self._by_email: dict[str, UUID] = {}

    async def add(self, user: User) -> User:
        self._users[user.id] = user
        self._by_email[user.email] = user.id
        return user

    async def get(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        user_id = self._by_email.get(email)
        return self._users.get(user_id) if user_id is not None else None


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


def make_user(
    email: str = "alice@example.com",
    password: str = "supersecret1",
    password_hash: str | None = None,
) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=password_hash or f"hashed:{password}",
    )


def frozen_now() -> datetime:
    return datetime.now(UTC)
