"""Use case: partially update a task.

`TaskChanges` uses the `UNSET` sentinel so that "field not provided"
can be distinguished from "field explicitly set to None" (which means
'clear the description').
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.common import UNSET, UnsetType, is_set
from app.domain.entities.task import (
    Task,
    TaskStatus,
    validate_description,
    validate_title,
)
from app.domain.exceptions import NotFoundError
from app.domain.ports.task_repository import TaskRepository


@dataclass
class TaskChanges:
    title: str | UnsetType = UNSET
    description: str | UnsetType | None = UNSET
    status: TaskStatus | UnsetType = UNSET

    def has_changes(self) -> bool:
        return is_set(self.title) or is_set(self.description) or is_set(self.status)


class UpdateTaskUseCase:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    async def execute(self, *, task_id: UUID, owner_id: UUID, changes: TaskChanges) -> Task:
        task = await self._tasks.get_owned(task_id, owner_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")

        if is_set(changes.title):
            task.title = validate_title(changes.title)
        if is_set(changes.description):
            task.description = validate_description(changes.description)
        if is_set(changes.status):
            task.change_status(changes.status)
        return await self._tasks.save(task)
