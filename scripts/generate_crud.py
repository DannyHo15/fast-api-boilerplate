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
and `body` (optional, text). Endpoints require auth (CurrentUser) but are
NOT user-scoped - to scope per user, follow `tasks.py` as the reference.

After generating, run:
    make revision m="create notes table"   # autogenerate the migration
    make migrate
    make test
"""

from __future__ import annotations

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
    if not re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name or ""):
        sys.exit(
            f"error: invalid resource name {name!r} - use lowercase snake_case "
            "(e.g. 'note', 'user_profile')"
        )


# ---------------------------------------------------------------------------
# Helpers for patching existing files
# ---------------------------------------------------------------------------


def add_import(path: Path, new_import: str) -> None:
    """Insert `new_import` into the contiguous `app.*` import block, sorted."""
    lines = path.read_text(encoding="utf-8").splitlines()

    def is_app_import(line: str) -> bool:
        s = line.strip()
        return s.startswith("from app.") or s.startswith("import app.")

    idxs = [i for i, line in enumerate(lines) if is_app_import(line)]
    if not idxs:
        sys.exit(f"error: no `app.*` import block found in {path}")
    start, end = idxs[0], idxs[-1]
    if end - start + 1 != len(idxs):
        sys.exit(f"error: `app.*` import block in {path} is not contiguous")

    imports = lines[start : end + 1]
    if new_import in imports:
        return  # idempotent
    imports.append(new_import)

    def sort_key(line: str) -> tuple[str, str]:
        s = line.strip()
        if s.startswith("import "):
            return (s.split()[1], "")
        head, tail = s.split("import", 1)
        module = head.split()[-1]
        first_name = tail.strip().split(",")[0].strip()
        return (module, first_name)

    imports.sort(key=sort_key)
    lines[start : end + 1] = imports
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_line_to_single_import(path: Path, module: str, name: str) -> None:
    """Add `name` to `from <module> import a, b, c` (sorted, idempotent)."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^from {re.escape(module)} import (.+)$", text, flags=re.M)
    if match is None:
        sys.exit(f"error: import from {module} not found in {path}")
    names = [n.strip() for n in match.group(1).split(",")]
    if name in names:
        return
    names.append(name)
    names.sort()
    text = text.replace(
        match.group(0), f"from {module} import " + ", ".join(names), 1
    )
    path.write_text(text, encoding="utf-8")


def append_block(path: Path, marker: str, block: str) -> None:
    """Append `block` at EOF, guarded by `marker` (idempotent)."""
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block, encoding="utf-8")


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
    title: str
    body: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(cls, *, title: str, body: str | None = None) -> ${pascal}:
        """Create a new ${snake}, enforcing business rules."""
        return cls(id=uuid4(), title=validate_title(title), body=validate_body(body))

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

    async def get(self, ${snake}_id: UUID) -> ${pascal} | None:
        ...

    async def list_all(
        self, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[${pascal}], int]:
        """Return a page of ${plural} plus the total count."""
        ...

    async def save(self, ${snake}: ${pascal}) -> ${pascal}:
        """Persist changes to an existing ${snake}."""
        ...

    async def delete(self, ${snake}_id: UUID) -> bool:
        """Delete the ${snake}. Returns success."""
        ...
'''

APP_INIT = '"""${pascal} use cases."""\n'

CREATE_USECASE = '''\
"""Use case: create a ${snake}."""

from dataclasses import dataclass

from app.domain.entities.${snake} import ${pascal}
from app.domain.ports.${snake}_repository import ${pascal}Repository


@dataclass(frozen=True, slots=True)
class Create${pascal}Input:
    title: str
    body: str | None = None


class Create${pascal}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(self, input: Create${pascal}Input) -> ${pascal}:
        ${snake} = ${pascal}.create(title=input.title, body=input.body)
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

    async def execute(self, ${snake}_id: UUID) -> ${pascal}:
        ${snake} = await self._${plural}.get(${snake}_id)
        if ${snake} is None:
            raise NotFoundError(f"${pascal} {{{${snake}_id}}} not found")
        return ${snake}
'''

LIST_USECASE = '''\
"""Use case: list ${plural} with pagination."""

from dataclasses import dataclass

from app.application.common import Page
from app.domain.entities.${snake} import ${pascal}
from app.domain.exceptions import DomainError
from app.domain.ports.${snake}_repository import ${pascal}Repository

MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class List${pascal_plural}Input:
    offset: int = 0
    limit: int = 20


class List${pascal_plural}UseCase:
    def __init__(self, ${plural}: ${pascal}Repository) -> None:
        self._${plural} = ${plural}

    async def execute(self, input: List${pascal_plural}Input) -> Page[${pascal}]:
        if input.offset < 0:
            raise DomainError("offset must be >= 0")
        if not MIN_PAGE_SIZE <= input.limit <= MAX_PAGE_SIZE:
            raise DomainError(f"limit must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}")

        items, total = await self._${plural}.list_all(
            offset=input.offset, limit=input.limit
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
        self, *, ${snake}_id: UUID, changes: ${pascal}Changes
    ) -> ${pascal}:
        ${snake} = await self._${plural}.get(${snake}_id)
        if ${snake} is None:
            raise NotFoundError(f"${pascal} {{{${snake}_id}}} not found")

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

    async def execute(self, ${snake}_id: UUID) -> None:
        deleted = await self._${plural}.delete(${snake}_id)
        if not deleted:
            raise NotFoundError(f"${pascal} {{{${snake}_id}}} not found")
'''

ORM_MODEL = '''\
"""ORM model for ${plural}."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ${pascal}Model(Base):
    __tablename__ = "${plural}"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
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
        return f"<${pascal}Model id={{{self.id}}} title={{{self.title!r}}}>"
'''

REPOSITORY = '''\
"""SQLAlchemy implementation of `app.domain.ports.${snake}_repository.${pascal}Repository`."""

from uuid import UUID

from sqlalchemy import func, select
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

    async def get(self, ${snake}_id: UUID) -> ${pascal} | None:
        model = await self._session.get(${pascal}Model, ${snake}_id)
        return ${snake}_to_domain(model) if model is not None else None

    async def list_all(
        self, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[${pascal}], int]:
        base = select(${pascal}Model)
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
            raise NotFoundError(f"${pascal} {{{${snake}.id}}} not found")
        model.title = ${snake}.title
        model.body = ${snake}.body
        model.updated_at = ${snake}.updated_at
        await self._session.flush()
        return ${snake}_to_domain(model)

    async def delete(self, ${snake}_id: UUID) -> bool:
        model = await self._session.get(${pascal}Model, ${snake}_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
'''

MAPPER_BLOCK = '''\
def ${snake}_to_domain(model: ${pascal}Model) -> ${pascal}:
    return ${pascal}(
        id=model.id,
        title=model.title,
        body=model.body,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def ${snake}_to_model(${snake}: ${pascal}) -> ${pascal}Model:
    return ${pascal}Model(
        id=${snake}.id,
        title=${snake}.title,
        body=${snake}.body,
        created_at=${snake}.created_at,
        updated_at=${snake}.updated_at,
    )
'''

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
"""${pascal} endpoints (full CRUD). Generated - adjust as needed."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, ${pascal}RepositoryDep
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
from app.core.config import get_settings
from app.domain.entities.${snake} import ${pascal}

router = APIRouter()

_settings = get_settings()


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
        Create${pascal}Input(title=payload.title, body=payload.body)
    )


@router.get(
    "",
    response_model=Page[${pascal}Read],
    summary="List ${plural}",
)
async def list_${plural}(
    ${plural}: ${pascal}RepositoryDep,
    user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_settings.max_page_size)] = (
        _settings.default_page_size
    ),
) -> Page[${pascal}Read]:
    page = await List${pascal_plural}UseCase(${plural}).execute(
        List${pascal_plural}Input(offset=offset, limit=limit)
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
    return await usecase.execute(${snake}_id)


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
        ${snake}_id=${snake}_id, changes=_build_changes(payload)
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
    await usecase.execute(${snake}_id)
'''

DEPS_BLOCK = '''\
def get_${snake}_repository(session: SessionDep) -> SqlAlchemy${pascal}Repository:
    return SqlAlchemy${pascal}Repository(session)


${pascal}RepositoryDep = Annotated[
    SqlAlchemy${pascal}Repository, Depends(get_${snake}_repository)
]
'''

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


class InMemory${pascal}Repository:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, ${pascal}] = {}

    async def add(self, ${snake}: ${pascal}) -> ${pascal}:
        self._items[${snake}.id] = ${snake}
        return ${snake}

    async def get(self, ${snake}_id: uuid.UUID) -> ${pascal} | None:
        return self._items.get(${snake}_id)

    async def list_all(
        self, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[${pascal}], int]:
        items = sorted(
            self._items.values(), key=lambda t: (t.created_at, t.id), reverse=True
        )
        return items[offset : offset + limit], len(items)

    async def save(self, ${snake}: ${pascal}) -> ${pascal}:
        self._items[${snake}.id] = ${snake}
        return ${snake}

    async def delete(self, ${snake}_id: uuid.UUID) -> bool:
        return self._items.pop(${snake}_id, None) is not None


async def test_create_${snake}_persists_and_trims() -> None:
    repo = InMemory${pascal}Repository()
    ${snake} = await Create${pascal}UseCase(repo).execute(
        Create${pascal}Input(title="  Hello  ", body="  World  ")
    )
    assert ${snake}.title == "Hello"
    assert ${snake}.body == "World"
    assert await repo.get(${snake}.id) is not None


async def test_create_${snake}_rejects_blank_title() -> None:
    usecase = Create${pascal}UseCase(InMemory${pascal}Repository())
    with pytest.raises(DomainError):
        await usecase.execute(Create${pascal}Input(title="   "))


async def test_get_${snake}_found() -> None:
    repo = InMemory${pascal}Repository()
    created = await Create${pascal}UseCase(repo).execute(
        Create${pascal}Input(title="t")
    )
    result = await Get${pascal}UseCase(repo).execute(created.id)
    assert result.id == created.id


async def test_get_${snake}_missing_raises_not_found() -> None:
    usecase = Get${pascal}UseCase(InMemory${pascal}Repository())
    with pytest.raises(NotFoundError):
        await usecase.execute(uuid.uuid4())


async def test_list_${plural}_pagination() -> None:
    repo = InMemory${pascal}Repository()
    for i in range(5):
        await Create${pascal}UseCase(repo).execute(
            Create${pascal}Input(title=f"${snake} {{{i}}}")
        )
    page = await List${pascal_plural}UseCase(repo).execute(
        List${pascal_plural}Input(offset=0, limit=2)
    )
    assert len(page.items) == 2
    assert page.total == 5
    assert page.has_more is True


async def test_update_${snake}_partial_and_clear_body() -> None:
    repo = InMemory${pascal}Repository()
    created = await Create${pascal}UseCase(repo).execute(
        Create${pascal}Input(title="old", body="old body")
    )
    updated = await Update${pascal}UseCase(repo).execute(
        ${snake}_id=created.id, changes=${pascal}Changes(title="new")
    )
    assert updated.title == "new"
    assert updated.body == "old body"  # untouched

    cleared = await Update${pascal}UseCase(repo).execute(
        ${snake}_id=created.id, changes=${pascal}Changes(body=None)
    )
    assert cleared.body is None


async def test_delete_${snake}() -> None:
    repo = InMemory${pascal}Repository()
    created = await Create${pascal}UseCase(repo).execute(Create${pascal}Input(title="t"))
    usecase = Delete${pascal}UseCase(repo)

    await usecase.execute(created.id)
    assert await repo.get(created.id) is None

    with pytest.raises(NotFoundError):
        await usecase.execute(created.id)
'''

INTEGRATION_TEST = '''\
"""Integration tests: full ${plural} CRUD flow over HTTP.

Generated by scripts/generate_crud.py - extend as the ${snake} rules grow.
"""

from tests.helpers import auth_headers, register_and_login


async def _token(client) -> str:
    body = await register_and_login(client)
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
    response = await client.get(f"/v1/${plural}/{{{item_id}}}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == item_id

    # List
    listing = (await client.get("/v1/${plural}", headers=headers)).json()
    assert listing["meta"]["total"] == 1
    assert listing["items"][0]["id"] == item_id

    # Update (partial + clear body)
    response = await client.patch(
        f"/v1/${plural}/{{{item_id}}}",
        json={"title": "Updated", "body": None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert response.json()["body"] is None

    # Delete
    assert (
        await client.delete(f"/v1/${plural}/{{{item_id}}}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"/v1/${plural}/{{{item_id}}}", headers=headers)
    ).status_code == 404
    assert (
        await client.get(f"/v1/${plural}/{{{item_id}}}", headers=headers)
    ).json()["error"]["code"] == "NOT_FOUND"


async def test_${plural}_require_authentication(client) -> None:
    assert (
        await client.post("/v1/${plural}", json={"title": "x"})
    ).status_code == 401
    assert (await client.get("/v1/${plural}")).status_code == 401


async def test_create_${snake}_validation_error_shape(client) -> None:
    headers = auth_headers(await _token(client))
    response = await client.post(
        "/v1/${plural}", json={"title": ""}, headers=headers
    )
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


def write_new_file(path: Path, content: str, created: list[Path]) -> None:
    if path.exists():
        sys.exit(f"error: refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(path)


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

    entity_path = ROOT / f"src/app/domain/entities/{snake}.py"
    if entity_path.exists():
        sys.exit(
            f"error: resource {name!r} already exists ({entity_path}). "
            "Delete its files first (see the generated list below)."
        )

    created: list[Path] = []

    # --- new files ---------------------------------------------------------
    files: dict[str, str] = {
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
    for rel, template in files.items():
        write_new_file(ROOT / rel, render(template, m), created)

    # --- patched files ------------------------------------------------------
    # 1. models/__init__.py: register the new ORM model
    add_import(
        ROOT / "src/app/infrastructure/database/models/__init__.py",
        f"from app.infrastructure.database.models.{snake} import "
        f"{pascal}Model as {pascal}Model",
    )

    # 2. mappers.py: import + mapper functions
    mappers = ROOT / "src/app/infrastructure/database/mappers.py"
    add_import(mappers, f"from app.domain.entities.{snake} import {pascal}")
    add_import(
        mappers,
        f"from app.infrastructure.database.models.{snake} import {pascal}Model",
    )
    append_block(
        mappers,
        f"def {snake}_to_domain(",
        render(MAPPER_BLOCK, m),
    )

    # 3. deps.py: repository dependency
    deps = ROOT / "src/app/api/deps.py"
    add_import(
        deps,
        f"from app.infrastructure.repositories.{snake}_repository import SqlAlchemy{pascal}Repository",
    )
    append_block(deps, f"def get_{snake}_repository(", render(DEPS_BLOCK, m))

    # 4. v1 router: import + registration
    router = ROOT / "src/app/api/v1/router.py"
    add_line_to_single_import(router, "app.api.v1.endpoints", snake)
    append_block(
        router,
        f"{snake}.router",
        f'api_router.include_router({snake}.router, prefix="/{plural}", tags=["{plural}"])',
    )

    # --- format (best effort) ------------------------------------------------
    for path in created:
        try:
            subprocess.run(
                [sys.executable, "-m", "ruff", "format", str(path)],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    for path in (mappers, deps, router):
        try:
            subprocess.run(
                [sys.executable, "-m", "ruff", "format", str(path)],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # --- summary --------------------------------------------------------------
    print(f"Generated {pascal} resource ({len(created)} new files):")
    for path in created:
        print(f"  + {path.relative_to(ROOT)}")
    print("Patched:")
    print(f"  ~ src/app/infrastructure/database/models/__init__.py (model registered)")
    print(f"  ~ src/app/infrastructure/database/mappers.py (mappers)")
    print(f"  ~ src/app/api/deps.py (repository dependency)")
    print(f"  ~ src/app/api/v1/router.py (router registered)")
    print()
    print("Endpoints (auth required): POST/GET /v1/" + plural
          + ", GET/PATCH/DELETE /v1/" + plural + "/{id}")
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
