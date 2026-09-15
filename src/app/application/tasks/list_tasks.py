"""Use case: list a user's tasks with pagination and optional filter."""

from dataclasses import dataclass
from uuid import UUID

from app.application.common import Page
from app.domain.entities.task import Task, TaskStatus
from app.domain.exceptions import DomainError
from app.domain.ports.task_repository import TaskRepository

MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class ListTasksInput:
    owner_id: UUID
    status: TaskStatus | None = None
    offset: int = 0
    limit: int = 20


class ListTasksUseCase:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    async def execute(self, input: ListTasksInput) -> Page[Task]:
        if input.offset < 0:
            raise DomainError("offset must be >= 0")
        if not MIN_PAGE_SIZE <= input.limit <= MAX_PAGE_SIZE:
            raise DomainError(f"limit must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}")

        items, total = await self._tasks.list_for_owner(
            input.owner_id,
            status=input.status,
            offset=input.offset,
            limit=input.limit,
        )
        return Page(items=items, total=total, offset=input.offset, limit=input.limit)
