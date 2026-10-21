"""Use case: create a task."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.task import Task
from app.domain.ports.task_repository import TaskRepository


@dataclass(frozen=True, slots=True)
class CreateTaskInput:
    owner_id: UUID
    title: str
    description: str | None = None


class CreateTaskUseCase:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    async def execute(self, input: CreateTaskInput) -> Task:
        task = Task.create(
            owner_id=input.owner_id,
            title=input.title,
            description=input.description,
        )
        return await self._tasks.add(task)
