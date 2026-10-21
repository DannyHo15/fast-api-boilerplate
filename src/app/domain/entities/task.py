"""Task entity and its business rules."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.exceptions import DomainError

MAX_TITLE_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 2000


class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


def validate_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise DomainError("Task title must not be empty")
    if len(cleaned) > MAX_TITLE_LENGTH:
        raise DomainError(f"Task title must be at most {MAX_TITLE_LENGTH} characters")
    return cleaned


def validate_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = description.strip()
    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        raise DomainError(f"Task description must be at most {MAX_DESCRIPTION_LENGTH} characters")
    return cleaned or None


@dataclass
class Task:
    id: UUID
    owner_id: UUID
    title: str
    status: TaskStatus
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        owner_id: UUID,
        title: str,
        description: str | None = None,
    ) -> Task:
        """Create a new task, enforcing business rules."""
        return cls(
            id=uuid4(),
            owner_id=owner_id,
            title=validate_title(title),
            status=TaskStatus.PENDING,
            description=validate_description(description),
        )

    def change_status(self, status: TaskStatus) -> None:
        self.status = status
        self.touch()

    def touch(self) -> None:
        """Mark the task as modified (bump `updated_at`)."""
        self.updated_at = datetime.now(UTC)
