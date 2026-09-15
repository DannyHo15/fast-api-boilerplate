"""Port for task persistence."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.task import Task, TaskStatus


class TaskRepository(Protocol):
    async def add(self, task: Task) -> Task:
        """Persist a new task and return the stored entity."""
        ...

    async def get(self, task_id: UUID) -> Task | None: ...

    async def get_owned(self, task_id: UUID, owner_id: UUID) -> Task | None:
        """Return the task only if it exists AND belongs to `owner_id`.

        Returning `None` (instead of the task) for foreign tasks avoids
        leaking the existence of other users' data.
        """
        ...

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        status: TaskStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        """Return a page of the owner's tasks plus the total count."""
        ...

    async def save(self, task: Task) -> Task:
        """Persist changes to an existing task."""
        ...

    async def delete(self, task_id: UUID, owner_id: UUID) -> bool:
        """Delete the task if it belongs to `owner_id`. Returns success."""
        ...
