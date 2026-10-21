#!/usr/bin/env python3
"""Generate a full CRUD resource following the boilerplate's Clean Architecture.

Usage:
    make crud name=notes
    # or
    .venv/bin/python scripts/generate_crud.py notes

What it generates (for `notes`, entity `Note`):

    domain layer
      src/app/domain/entities/notes.py                 entity + business rules
      src/app/domain/ports/note_repository.py          repository port (Protocol)
    application layer
      src/app/application/note/{__init__,create_note,get_note,list_note,
                                update_note,delete_note}.py
    infrastructure layer
      src/app/infrastructure/database/models/note.py   ORM model
      src/app/infrastructure/repositories/note_repository.py
      src/app/infrastructure/database/mappers.py       + mappers (appended)
    api layer
      src/app/api/schemas/note.py                      request/response DTOs
      src/app/api/v1/endpoints/note.py                 CRUD router
      src/app/api/deps.py                              + repository dependency
      src/app/api/v1/router.py                         + router registration
    tests
      tests/unit/application/test_note_usecases.py     fake in-memory repo
      tests/integration/test_notes.py                  full HTTP flow

The generated resource has two generic fields: `title` (required, string)
and `body` (optional, text). Like `tasks`, every record belongs to the user
who created it (`owner_id`): other users get 404 and never see it in lists.

All new and patched file contents are computed before anything is written,
so a failing check leaves the repository untouched.

After generating, run:
    make revision m="create notes table"   # autogenerate the migration
    make migrate
    make test
"""

from __future__ import annotations

import ast
import keyword
import re
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def pascal_case(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_") if part)


def pluralize(snake: str) -> str:
    if snake.endswith("s"):
        return snake
    if snake.endswith("y") and len(snake) > 1 and snake[-2] not in "aeiou":
        return snake[:-1] + "ies"
    return snake + "s"


def validate_name(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name or "") or keyword.iskeyword(name):
        sys.exit(
            f"error: invalid resource name {name!r} - use lowercase snake_case "
            "(e.g. 'note', 'user_profile')"
        )
    # The endpoint module is imported into router.py by this name: it must not
    # shadow anything already there (e.g. `rate_limited`, `api_router`).
    router_text = (ROOT / "src/app/api/v1/router.py").read_text(encoding="utf-8")
    if re.search(rf"\b{name}\b", router_text):
        sys.exit(f"error: {name!r} is already used in src/app/api/v1/router.py - pick another name")


# ---------------------------------------------------------------------------
# Helpers for patching existing files
# ---------------------------------------------------------------------------


def add_import(text: str, new_import: str) -> str:
    """Insert `new_import` after the last top-level import (ruff sorts it later).

    Uses the AST, so imports wrapped over several lines by ruff are handled.
    """
    if new_import in text.splitlines():
        return text  # idempotent
    imports = [n for n in ast.parse(text).body if isinstance(n, ast.Import | ast.ImportFrom)]
    if not imports:
        sys.exit("error: no top-level import found to anchor the new import")
    lines = text.splitlines(keepends=True)
    lines.insert(imports[-1].end_lineno or len(lines), new_import + "\n")
    return "".join(lines)


def append_block(text: str, marker: str, block: str) -> str:
    """Append `block` at EOF, guarded by `marker` (idempotent)."""
    if marker in text:
        return text
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + block


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

ENTITY = '''\
"""${pascal} entity and its business rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.exceptions import DomainError

MAX_TITLE_LENGTH = 255
MAX_BODY_LENGTH = 4000


def validate_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise DomainError("${pascal} title must not be empty")
    if len(cleaned) > MAX_TITLE_LENGTH:
        raise DomainError(f"${pascal} title must be at most {MAX_TITLE_LENGTH} characters")
    return cleaned


def validate_body(body: str | None) -> str | None:
    if body is None:
        return None
    cleaned = body.strip()
    if len(cleaned) > MAX_BODY_LENGTH:
        raise DomainError(f"${pascal} body must be at most {MAX_BODY_LENGTH} characters")
    return cleaned or None


@dataclass
class ${pascal}:
    id: UUID
    owner_id: UUID
    title: str
    body: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(cls, *, owner_id: UUID, title: str, body: str | None = None) -> ${pascal}:
        """Create a new ${snake}, enforcing business rules."""
        return cls(
            id=uuid4(),
            owner_id=owner_id,
            title=validate_title(title),
            body=validate_body(body),
        )

    def touch(self) -> None:
        """Mark the ${snake} as modified (bump `updated_at`)."""
        self.updated_at = datetime.now(UTC)
'''

PORT = '''\
"""Port for ${plural} persistence."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.${snake} import ${pascal}


class ${pascal}Repository(Protocol):
    async def add(self, ${snake}: ${pascal}) -> ${pascal}:
        """Persist a new ${snake} and return the stored entity."""
        ...

    async def get_owned(self, ${snake}_id: UUID, owner_id: UUID) -> ${pascal} | None:
        """Return the ${snake} only if it exists AND belongs to `owner_id`."""
        ...

    async def list_for_owner(
        self, owner_id: UUID, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[${pascal}], int]:
        """Return a page of the owner's ${plural} plus the total count."""
        ...

    async def save(self, ${snake}: ${pascal}) -> ${pascal}:
        """Persist changes to an existing ${snake}."""
        ...

    async def delete(self, ${snake}_id: UUID, owner_id: UUID) -> bool:
        """Delete the ${snake} if it belongs to `owner_id`. Returns success."""
        ...
'''

APP_INIT = '"""${pascal} use cases."""\n'

CREATE_USECASE = '''\
"""Use case: create a ${snake}."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.${snake} import ${pascal}
from app.domain.ports.${snake}_repository import ${pascal}Repository


@dataclass(frozen=True, slots=True)
class Create${pascal}Input:
    owner_id: UUID
    title: str
    body: str | None = None


class Create${pascal}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(self, input: Create${pascal}Input) -> ${pascal}:
        ${snake} = ${pascal}.create(owner_id=input.owner_id, title=input.title, body=input.body)
        return await self._${plural}.add(${snake})
'''

GET_USECASE = '''\
"""Use case: fetch a single ${snake}."""

from uuid import UUID

from app.domain.entities.${snake} import ${pascal}
from app.domain.exceptions import NotFoundError
from app.domain.ports.${snake}_repository import ${pascal}Repository


class Get${pascal}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(self, *, ${snake}_id: UUID, owner_id: UUID) -> ${pascal}:
        ${snake} = await self._${plural}.get_owned(${snake}_id, owner_id)
        if ${snake} is None:
            raise NotFoundError(f"${pascal} {${snake}_id} not found")
        return ${snake}
'''

LIST_USECASE = '''\
"""Use case: list ${plural} with pagination."""

from dataclasses import dataclass
from uuid import UUID

from app.application.common import Page
from app.domain.entities.${snake} import ${pascal}
from app.domain.exceptions import DomainError
from app.domain.ports.${snake}_repository import ${pascal}Repository

MIN_PAGE_SIZE = 1


@dataclass(frozen=True, slots=True)
class List${pascal_plural}Input:
    owner_id: UUID
    offset: int = 0
    limit: int = 20


class List${pascal_plural}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(self, input: List${pascal_plural}Input) -> Page[${pascal}]:
        if input.offset < 0:
            raise DomainError("offset must be >= 0")
        # The upper bound is MAX_PAGE_SIZE in settings, enforced by the API layer.
        if input.limit < MIN_PAGE_SIZE:
            raise DomainError(f"limit must be >= {MIN_PAGE_SIZE}")

        items, total = await self._${plural}.list_for_owner(
            input.owner_id, offset=input.offset, limit=input.limit
        )
        return Page(items=items, total=total, offset=input.offset, limit=input.limit)
'''

UPDATE_USECASE = '''\
"""Use case: partially update a ${snake}.

`${pascal}Changes` uses the `UNSET` sentinel so that "field not provided"
can be distinguished from "field explicitly set to None" (which means
'clear the body').
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.common import UNSET, UnsetType, is_set
from app.domain.entities.${snake} import ${pascal}, validate_body, validate_title
from app.domain.exceptions import NotFoundError
from app.domain.ports.${snake}_repository import ${pascal}Repository


@dataclass
class ${pascal}Changes:
    title: str | UnsetType = UNSET
    body: str | UnsetType | None = UNSET

    def has_changes(self) -> bool:
        return is_set(self.title) or is_set(self.body)


class Update${pascal}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(
        self, *, ${snake}_id: UUID, owner_id: UUID, changes: ${pascal}Changes
    ) -> ${pascal}:
        ${snake} = await self._${plural}.get_owned(${snake}_id, owner_id)
        if ${snake} is None:
            raise NotFoundError(f"${pascal} {${snake}_id} not found")

        if changes.has_changes():
            if is_set(changes.title):
                ${snake}.title = validate_title(changes.title)
            if is_set(changes.body):
                ${snake}.body = validate_body(changes.body)
            ${snake}.touch()
        return await self._${plural}.save(${snake})
'''

DELETE_USECASE = '''\
"""Use case: delete a ${snake}."""

from uuid import UUID

from app.domain.exceptions import NotFoundError
from app.domain.ports.${snake}_repository import ${pascal}Repository


class Delete${pascal}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(self, *, ${snake}_id: UUID, owner_id: UUID) -> None:
        deleted = await self._${plural}.delete(${snake}_id, owner_id)
        if not deleted:
            raise NotFoundError(f"${pascal} {${snake}_id} not found")
'''

ORM_MODEL = '''\
"""ORM model for ${plural}."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ${pascal}Model(Base):
    __tablename__ = "${plural}"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<${pascal}Model id={self.id} title={self.title!r}>"
'''

REPOSITORY = '''\
"""SQLAlchemy implementation of the `${pascal}Repository` port."""

from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.${snake} import ${pascal}
from app.domain.exceptions import NotFoundError
from app.infrastructure.database.mappers import ${snake}_to_domain, ${snake}_to_model
from app.infrastructure.database.models.${snake} import ${pascal}Model


class SqlAlchemy${pascal}Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, ${snake}: ${pascal}) -> ${pascal}:
        model = ${snake}_to_model(${snake})
        self._session.add(model)
        await self._session.flush()
        return ${snake}_to_domain(model)

    async def get_owned(self, ${snake}_id: UUID, owner_id: UUID) -> ${pascal} | None:
        stmt = select(${pascal}Model).where(
            ${pascal}Model.id == ${snake}_id, ${pascal}Model.owner_id == owner_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return ${snake}_to_domain(model) if model is not None else None

    async def list_for_owner(
        self, owner_id: UUID, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[${pascal}], int]:
        base = select(${pascal}Model).where(${pascal}Model.owner_id == owner_id)
        total = (
            await self._session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        stmt = (
            base.order_by(${pascal}Model.created_at.desc(), ${pascal}Model.id.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [${snake}_to_domain(m) for m in models], total

    async def save(self, ${snake}: ${pascal}) -> ${pascal}:
        model = await self._session.get(${pascal}Model, ${snake}.id)
        if model is None:
            raise NotFoundError(f"${pascal} {${snake}.id} not found")
        model.title = ${snake}.title
        model.body = ${snake}.body
        model.updated_at = ${snake}.updated_at
        await self._session.flush()
        return ${snake}_to_domain(model)

    async def delete(self, ${snake}_id: UUID, owner_id: UUID) -> bool:
        result = await self._session.execute(
            delete(${pascal}Model).where(
                ${pascal}Model.id == ${snake}_id, ${pascal}Model.owner_id == owner_id
            )
        )
        return cast(CursorResult[object], result).rowcount > 0
'''

MAPPER_BLOCK = """\
def ${snake}_to_domain(model: ${pascal}Model) -> ${pascal}:
    return ${pascal}(
        id=model.id,
        owner_id=model.owner_id,
        title=model.title,
        body=model.body,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def ${snake}_to_model(${snake}: ${pascal}) -> ${pascal}Model:
    return ${pascal}Model(
        id=${snake}.id,
        owner_id=${snake}.owner_id,
        title=${snake}.title,
        body=${snake}.body,
        created_at=${snake}.created_at,
        updated_at=${snake}.updated_at,
    )
"""

SCHEMA = '''\
"""${pascal} schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ${pascal}Create(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=4000)


class ${pascal}Update(BaseModel):
    """Partial update.

    - a field omitted from the payload is left unchanged,
    - `body: null` clears the body,
    - an explicit `null` for `title` is ignored (the domain requires it).
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=4000)


class ${pascal}Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
'''

ENDPOINT = '''\
"""${pascal} endpoints (CRUD, scoped to the authenticated user).

Generated by scripts/generate_crud.py - adjust as needed.
"""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, PageParamsDep, ${pascal}RepositoryDep
from app.api.schemas.common import Page, PageMeta
from app.api.schemas.${snake} import ${pascal}Create, ${pascal}Read, ${pascal}Update
from app.application.${snake}.create_${snake} import Create${pascal}Input, Create${pascal}UseCase
from app.application.${snake}.delete_${snake} import Delete${pascal}UseCase
from app.application.${snake}.get_${snake} import Get${pascal}UseCase
from app.application.${snake}.list_${snake} import (
    List${pascal_plural}Input,
    List${pascal_plural}UseCase,
)
from app.application.${snake}.update_${snake} import ${pascal}Changes, Update${pascal}UseCase
from app.domain.entities.${snake} import ${pascal}

router = APIRouter()


def _build_changes(payload: ${pascal}Update) -> ${pascal}Changes:
    """Translate the partial-update payload into `${pascal}Changes`."""
    changes = ${pascal}Changes()
    if "title" in payload.model_fields_set and payload.title is not None:
        changes.title = payload.title
    if "body" in payload.model_fields_set:
        changes.body = payload.body  # None means "clear it"
    return changes


@router.post(
    "",
    response_model=${pascal}Read,
    status_code=201,
    summary="Create a ${snake}",
)
async def create_${snake}(
    payload: ${pascal}Create,
    ${plural}: ${pascal}RepositoryDep,
    user: CurrentUser,
) -> ${pascal}:
    usecase = Create${pascal}UseCase(${plural})
    return await usecase.execute(
        Create${pascal}Input(owner_id=user.id, title=payload.title, body=payload.body)
    )


@router.get(
    "",
    response_model=Page[${pascal}Read],
    summary="List the authenticated user's ${plural}",
)
async def list_${plural}(
    ${plural}: ${pascal}RepositoryDep,
    user: CurrentUser,
    paging: PageParamsDep,
) -> Page[${pascal}Read]:
    page = await List${pascal_plural}UseCase(${plural}).execute(
        List${pascal_plural}Input(owner_id=user.id, offset=paging.offset, limit=paging.limit)
    )
    return Page[${pascal}Read](
        items=[${pascal}Read.model_validate(item) for item in page.items],
        meta=PageMeta(
            total=page.total,
            offset=page.offset,
            limit=page.limit,
            has_more=page.has_more,
        ),
    )


@router.get(
    "/{${snake}_id}",
    response_model=${pascal}Read,
    summary="Get a ${snake}",
)
async def get_${snake}(
    ${snake}_id: UUID,
    ${plural}: ${pascal}RepositoryDep,
    user: CurrentUser,
) -> ${pascal}:
    usecase = Get${pascal}UseCase(${plural})
    return await usecase.execute(${snake}_id=${snake}_id, owner_id=user.id)


@router.patch(
    "/{${snake}_id}",
    response_model=${pascal}Read,
    summary="Partially update a ${snake}",
)
async def update_${snake}(
    ${snake}_id: UUID,
    payload: ${pascal}Update,
    ${plural}: ${pascal}RepositoryDep,
    user: CurrentUser,
) -> ${pascal}:
    usecase = Update${pascal}UseCase(${plural})
    return await usecase.execute(
        ${snake}_id=${snake}_id, owner_id=user.id, changes=_build_changes(payload)
    )


@router.delete(
    "/{${snake}_id}",
    status_code=204,
    summary="Delete a ${snake}",
)
async def delete_${snake}(
    ${snake}_id: UUID,
    ${plural}: ${pascal}RepositoryDep,
    user: CurrentUser,
) -> None:
    usecase = Delete${pascal}UseCase(${plural})
    await usecase.execute(${snake}_id=${snake}_id, owner_id=user.id)
'''

DEPS_BLOCK = """\
def get_${snake}_repository(session: SessionDep) -> SqlAlchemy${pascal}Repository:
    return SqlAlchemy${pascal}Repository(session)


${pascal}RepositoryDep = Annotated[
    SqlAlchemy${pascal}Repository, Depends(get_${snake}_repository)
]
"""

UNIT_TEST = '''\
"""Unit tests for ${pascal} use cases (against an in-memory repository fake).

Generated by scripts/generate_crud.py - extend as the ${snake} rules grow.
"""

import uuid

import pytest

from app.application.${snake}.create_${snake} import (
    Create${pascal}Input,
    Create${pascal}UseCase,
)
from app.application.${snake}.delete_${snake} import Delete${pascal}UseCase
from app.application.${snake}.get_${snake} import Get${pascal}UseCase
from app.application.${snake}.list_${snake} import (
    List${pascal_plural}Input,
    List${pascal_plural}UseCase,
)
from app.application.${snake}.update_${snake} import ${pascal}Changes, Update${pascal}UseCase
from app.domain.entities.${snake} import ${pascal}
from app.domain.exceptions import DomainError, NotFoundError

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()


class InMemory${pascal}Repository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, ${pascal}] = {}

    async def add(self, ${snake}: ${pascal}) -> ${pascal}:
        self._items[${snake}.id] = ${snake}
        return ${snake}

    async def get_owned(self, ${snake}_id: uuid.UUID, owner_id: uuid.UUID) -> ${pascal} | None:
        item = self._items.get(${snake}_id)
        return item if item is not None and item.owner_id == owner_id else None

    async def list_for_owner(
        self, owner_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[${pascal}], int]:
        items = sorted(
            (t for t in self._items.values() if t.owner_id == owner_id),
            key=lambda t: (t.created_at, t.id),
            reverse=True,
        )
        return items[offset : offset + limit], len(items)

    async def save(self, ${snake}: ${pascal}) -> ${pascal}:
        self._items[${snake}.id] = ${snake}
        return ${snake}

    async def delete(self, ${snake}_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        if await self.get_owned(${snake}_id, owner_id) is None:
            return False
        del self._items[${snake}_id]
        return True


async def _create(
    repo: InMemory${pascal}Repository, title: str = "t", body: str | None = None
) -> ${pascal}:
    return await Create${pascal}UseCase(repo).execute(
        Create${pascal}Input(owner_id=OWNER, title=title, body=body)
    )


async def test_create_${snake}_persists_and_trims() -> None:
    repo = InMemory${pascal}Repository()
    ${snake} = await _create(repo, "  Hello  ", body="  World  ")
    assert ${snake}.title == "Hello"
    assert ${snake}.body == "World"
    assert ${snake}.owner_id == OWNER
    assert await repo.get_owned(${snake}.id, OWNER) is not None


async def test_create_${snake}_rejects_blank_title() -> None:
    with pytest.raises(DomainError):
        await _create(InMemory${pascal}Repository(), "   ")


async def test_get_${snake}_found() -> None:
    repo = InMemory${pascal}Repository()
    created = await _create(repo)
    result = await Get${pascal}UseCase(repo).execute(${snake}_id=created.id, owner_id=OWNER)
    assert result.id == created.id


async def test_get_${snake}_of_another_owner_raises_not_found() -> None:
    repo = InMemory${pascal}Repository()
    created = await _create(repo)
    with pytest.raises(NotFoundError):
        await Get${pascal}UseCase(repo).execute(${snake}_id=created.id, owner_id=OTHER)


async def test_list_${plural}_pagination_is_per_owner() -> None:
    repo = InMemory${pascal}Repository()
    for i in range(5):
        await _create(repo, f"${snake} {i}")
    page = await List${pascal_plural}UseCase(repo).execute(
        List${pascal_plural}Input(owner_id=OWNER, offset=0, limit=2)
    )
    assert len(page.items) == 2
    assert page.total == 5
    assert page.has_more is True

    other = await List${pascal_plural}UseCase(repo).execute(
        List${pascal_plural}Input(owner_id=OTHER)
    )
    assert other.total == 0


async def test_update_${snake}_partial_and_clear_body() -> None:
    repo = InMemory${pascal}Repository()
    created = await _create(repo, "old", body="old body")
    usecase = Update${pascal}UseCase(repo)
    updated = await usecase.execute(
        ${snake}_id=created.id, owner_id=OWNER, changes=${pascal}Changes(title="new")
    )
    assert updated.title == "new"
    assert updated.body == "old body"  # untouched

    cleared = await usecase.execute(
        ${snake}_id=created.id, owner_id=OWNER, changes=${pascal}Changes(body=None)
    )
    assert cleared.body is None


async def test_delete_${snake}() -> None:
    repo = InMemory${pascal}Repository()
    created = await _create(repo)
    usecase = Delete${pascal}UseCase(repo)

    with pytest.raises(NotFoundError):
        await usecase.execute(${snake}_id=created.id, owner_id=OTHER)

    await usecase.execute(${snake}_id=created.id, owner_id=OWNER)
    assert await repo.get_owned(created.id, OWNER) is None

    with pytest.raises(NotFoundError):
        await usecase.execute(${snake}_id=created.id, owner_id=OWNER)
'''

INTEGRATION_TEST = '''\
"""Integration tests: full ${plural} CRUD flow over HTTP.

Generated by scripts/generate_crud.py - extend as the ${snake} rules grow.
"""

from tests.helpers import auth_headers, register_and_login


async def _token(client, email: str = "alice@example.com") -> str:
    body = await register_and_login(client, email=email)
    return body["access_token"]


async def test_full_${snake}_crud_flow(client) -> None:
    headers = auth_headers(await _token(client))

    # Create
    response = await client.post(
        "/v1/${plural}",
        json={"title": "  Hello  ", "body": "  World  "},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["title"] == "Hello"
    assert item["body"] == "World"
    item_id = item["id"]

    # Read
    response = await client.get(f"/v1/${plural}/{item_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == item_id

    # List
    listing = (await client.get("/v1/${plural}", headers=headers)).json()
    assert listing["meta"]["total"] == 1
    assert listing["items"][0]["id"] == item_id

    # Update (partial + clear body)
    response = await client.patch(
        f"/v1/${plural}/{item_id}",
        json={"title": "Updated", "body": None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert response.json()["body"] is None

    # Delete
    assert (await client.delete(f"/v1/${plural}/{item_id}", headers=headers)).status_code == 204
    response = await client.get(f"/v1/${plural}/{item_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_${plural}_are_scoped_to_their_owner(client) -> None:
    alice = auth_headers(await _token(client, "alice@example.com"))
    bob = auth_headers(await _token(client, "bob@example.com"))

    item_id = (
        await client.post("/v1/${plural}", json={"title": "alice only"}, headers=alice)
    ).json()["id"]

    # Bob cannot see, update, or delete Alice's ${snake}.
    assert (await client.get(f"/v1/${plural}/{item_id}", headers=bob)).status_code == 404
    assert (
        await client.patch(f"/v1/${plural}/{item_id}", json={"title": "x"}, headers=bob)
    ).status_code == 404
    assert (await client.delete(f"/v1/${plural}/{item_id}", headers=bob)).status_code == 404
    assert (await client.get("/v1/${plural}", headers=bob)).json()["meta"]["total"] == 0

    # Alice's ${snake} is intact.
    response = await client.get(f"/v1/${plural}/{item_id}", headers=alice)
    assert response.json()["title"] == "alice only"


async def test_${plural}_require_authentication(client) -> None:
    assert (await client.post("/v1/${plural}", json={"title": "x"})).status_code == 401
    assert (await client.get("/v1/${plural}")).status_code == 401


async def test_create_${snake}_validation_error_shape(client) -> None:
    headers = auth_headers(await _token(client))
    response = await client.post("/v1/${plural}", json={"title": ""}, headers=headers)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]
'''


def render(template: str, mapping: dict[str, str]) -> str:
    return string.Template(template).substitute(mapping)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def run_ruff(paths: list[Path]) -> None:
    """Sort imports (merges the inserted ones) and format. Best effort."""
    args = [str(p) for p in paths]
    for cmd in (["check", "--select", "I", "--fix", "--quiet"], ["format", "--quiet"]):
        try:
            subprocess.run(
                [sys.executable, "-m", "ruff", *cmd, *args],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("warning: ruff unavailable or failed - run `make format` yourself")
            return


def generate(name: str) -> None:
    validate_name(name)
    snake = name
    plural = pluralize(name)
    pascal = pascal_case(name)
    pascal_plural = pascal_case(plural)
    m = {
        "snake": snake,
        "plural": plural,
        "pascal": pascal,
        "pascal_plural": pascal_plural,
    }

    # --- new files (checked before anything is written) ---------------------
    templates: dict[str, str] = {
        f"src/app/domain/entities/{snake}.py": ENTITY,
        f"src/app/domain/ports/{snake}_repository.py": PORT,
        f"src/app/application/{snake}/__init__.py": APP_INIT,
        f"src/app/application/{snake}/create_{snake}.py": CREATE_USECASE,
        f"src/app/application/{snake}/get_{snake}.py": GET_USECASE,
        f"src/app/application/{snake}/list_{snake}.py": LIST_USECASE,
        f"src/app/application/{snake}/update_{snake}.py": UPDATE_USECASE,
        f"src/app/application/{snake}/delete_{snake}.py": DELETE_USECASE,
        f"src/app/infrastructure/database/models/{snake}.py": ORM_MODEL,
        f"src/app/infrastructure/repositories/{snake}_repository.py": REPOSITORY,
        f"src/app/api/schemas/{snake}.py": SCHEMA,
        f"src/app/api/v1/endpoints/{snake}.py": ENDPOINT,
        f"tests/unit/application/test_{snake}_usecases.py": UNIT_TEST,
        f"tests/integration/test_{plural}.py": INTEGRATION_TEST,
    }
    new_files = {ROOT / rel: render(t, m) for rel, t in templates.items()}
    existing = [p for p in new_files if p.exists()]
    if existing:
        sys.exit(
            f"error: resource {name!r} (or a file it needs) already exists:\n"
            + "\n".join(f"  {p.relative_to(ROOT)}" for p in existing)
        )

    # --- patched files (computed in memory) --------------------------------
    models_init = ROOT / "src/app/infrastructure/database/models/__init__.py"
    mappers = ROOT / "src/app/infrastructure/database/mappers.py"
    deps = ROOT / "src/app/api/deps.py"
    router = ROOT / "src/app/api/v1/router.py"

    text = models_init.read_text(encoding="utf-8")
    patched = {
        models_init: add_import(
            text,
            f"from app.infrastructure.database.models.{snake} import "
            f"{pascal}Model as {pascal}Model",
        )
    }

    text = mappers.read_text(encoding="utf-8")
    text = add_import(text, f"from app.domain.entities.{snake} import {pascal}")
    text = add_import(text, f"from app.infrastructure.database.models.{snake} import {pascal}Model")
    patched[mappers] = append_block(text, f"def {snake}_to_domain(", render(MAPPER_BLOCK, m))

    text = deps.read_text(encoding="utf-8")
    text = add_import(
        text,
        f"from app.infrastructure.repositories.{snake}_repository import "
        f"SqlAlchemy{pascal}Repository",
    )
    patched[deps] = append_block(text, f"def get_{snake}_repository(", render(DEPS_BLOCK, m))

    text = router.read_text(encoding="utf-8")
    text = add_import(text, f"from app.api.v1.endpoints import {snake}")
    patched[router] = append_block(
        text,
        f"({snake}.router",
        f"api_router.include_router(\n    {snake}.router,"
        f' prefix="/{plural}", tags=["{plural}"], dependencies=rate_limited\n)\n',
    )

    # --- write --------------------------------------------------------------
    for path, content in {**new_files, **patched}.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    run_ruff([*new_files, *patched])

    # --- summary --------------------------------------------------------------
    print(f"Generated {pascal} resource ({len(new_files)} new files):")
    for path in new_files:
        print(f"  + {path.relative_to(ROOT)}")
    print("Patched:")
    for path in patched:
        print(f"  ~ {path.relative_to(ROOT)}")
    print()
    print(
        f"Endpoints (auth required, scoped to the caller): POST/GET /v1/{plural}, "
        f"GET/PATCH/DELETE /v1/{plural}/{{id}}"
    )
    print()
    print("Next steps:")
    print(f'  1. make revision m="create {plural} table"   # autogenerate migration')
    print("  2. make migrate")
    print("  3. make test")
    print(f"  4. Review the generated fields (title, body) and adjust for {pascal}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: generate_crud.py <resource_name>   (e.g. 'notes')")
    generate(sys.argv[1])
