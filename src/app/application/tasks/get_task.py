"""Use case: fetch a single task (with ownership check)."""

from uuid import UUID

from app.domain.entities.task import Task
from app.domain.exceptions import NotFoundError
from app.domain.ports.task_repository import TaskRepository


class GetTaskUseCase:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    async def execute(self, *, task_id: UUID, owner_id: UUID) -> Task:
        task = await self._tasks.get_owned(task_id, owner_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task
