"""Use case: delete a task (with ownership check)."""

from uuid import UUID

from app.domain.exceptions import NotFoundError
from app.domain.ports.task_repository import TaskRepository


class DeleteTaskUseCase:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    async def execute(self, *, task_id: UUID, owner_id: UUID) -> None:
        deleted = await self._tasks.delete(task_id, owner_id)
        if not deleted:
            raise NotFoundError(f"Task {task_id} not found")
