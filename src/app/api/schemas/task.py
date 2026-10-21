"""Task schemas.

The `TaskStatus` enum is reused straight from the domain - it is a plain
Python `enum.Enum`, so Pydantic handles (de)serialization for free.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.task import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255, examples=["Write tests"])
    description: str | None = Field(
        default=None, max_length=2000, examples=["Cover the task use cases"]
    )


class TaskUpdate(BaseModel):
    """Partial update.

    Semantics:
    - a field omitted from the payload is left unchanged,
    - `description: null` clears the description,
    - an explicit `null` for `title`/`status` is ignored (the domain
      requires those to be set).
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    status: TaskStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
