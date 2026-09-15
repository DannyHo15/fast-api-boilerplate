"""Unit tests for task use cases (against the in-memory repository fake)."""

import uuid

import pytest

from app.application.tasks.create_task import CreateTaskInput, CreateTaskUseCase
from app.application.tasks.delete_task import DeleteTaskUseCase
from app.application.tasks.get_task import GetTaskUseCase
from app.application.tasks.list_tasks import ListTasksInput, ListTasksUseCase
from app.application.tasks.update_task import TaskChanges, UpdateTaskUseCase
from app.domain.entities.task import TaskStatus
from app.domain.exceptions import DomainError, NotFoundError
from tests.unit.application.fakes import InMemoryTaskRepository

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()


async def test_create_task_persists_and_trims() -> None:
    repo = InMemoryTaskRepository()
    usecase = CreateTaskUseCase(repo)

    task = await usecase.execute(CreateTaskInput(owner_id=OWNER, title="  Buy milk  "))

    assert task.title == "Buy milk"
    assert task.owner_id == OWNER
    assert task.status is TaskStatus.PENDING
    assert await repo.get(task.id) is not None


async def test_create_task_rejects_blank_title() -> None:
    usecase = CreateTaskUseCase(InMemoryTaskRepository())
    with pytest.raises(DomainError):
        await usecase.execute(CreateTaskInput(owner_id=OWNER, title="   "))


async def test_get_task_found() -> None:
    repo = InMemoryTaskRepository()
    created = await CreateTaskUseCase(repo).execute(CreateTaskInput(owner_id=OWNER, title="t"))
    task = await GetTaskUseCase(repo).execute(task_id=created.id, owner_id=OWNER)
    assert task.id == created.id


async def test_get_task_missing_or_foreign_raises_not_found() -> None:
    repo = InMemoryTaskRepository()
    created = await CreateTaskUseCase(repo).execute(CreateTaskInput(owner_id=OWNER, title="t"))
    usecase = GetTaskUseCase(repo)

    with pytest.raises(NotFoundError):
        await usecase.execute(task_id=uuid.uuid4(), owner_id=OWNER)
    with pytest.raises(NotFoundError):
        # exists, but belongs to someone else
        await usecase.execute(task_id=created.id, owner_id=OTHER)


async def test_list_tasks_pagination_and_filter() -> None:
    repo = InMemoryTaskRepository()
    create = CreateTaskUseCase(repo)
    for i in range(5):
        await create.execute(CreateTaskInput(owner_id=OWNER, title=f"task {i}"))
    foreign = await create.execute(CreateTaskInput(owner_id=OTHER, title="foreign"))
    foreign.change_status(TaskStatus.DONE)
    await repo.save(foreign)

    usecase = ListTasksUseCase(repo)

    page = await usecase.execute(ListTasksInput(owner_id=OWNER, offset=0, limit=2))
    assert len(page.items) == 2
    assert page.total == 5  # foreign task is not counted
    assert page.has_more is True

    filtered = await usecase.execute(ListTasksInput(owner_id=OWNER, status=TaskStatus.PENDING))
    assert filtered.total == 5

    empty = await usecase.execute(ListTasksInput(owner_id=OWNER, offset=5, limit=2))
    assert empty.items == []
    assert empty.has_more is False


async def test_list_tasks_rejects_bad_pagination() -> None:
    usecase = ListTasksUseCase(InMemoryTaskRepository())
    with pytest.raises(DomainError):
        await usecase.execute(ListTasksInput(owner_id=OWNER, offset=-1))
    with pytest.raises(DomainError):
        await usecase.execute(ListTasksInput(owner_id=OWNER, limit=0))


async def test_update_task_partial() -> None:
    repo = InMemoryTaskRepository()
    created = await CreateTaskUseCase(repo).execute(
        CreateTaskInput(owner_id=OWNER, title="old", description="old desc")
    )
    usecase = UpdateTaskUseCase(repo)

    updated = await usecase.execute(
        task_id=created.id,
        owner_id=OWNER,
        changes=TaskChanges(title="new", status=TaskStatus.IN_PROGRESS),
    )
    assert updated.title == "new"
    assert updated.description == "old desc"  # untouched
    assert updated.status is TaskStatus.IN_PROGRESS

    # description: None clears it
    cleared = await usecase.execute(
        task_id=created.id,
        owner_id=OWNER,
        changes=TaskChanges(description=None),
    )
    assert cleared.description is None


async def test_update_task_no_changes_is_noop() -> None:
    repo = InMemoryTaskRepository()
    created = await CreateTaskUseCase(repo).execute(CreateTaskInput(owner_id=OWNER, title="t"))
    usecase = UpdateTaskUseCase(repo)
    result = await usecase.execute(task_id=created.id, owner_id=OWNER, changes=TaskChanges())
    assert result.title == "t"
    assert result.updated_at == created.updated_at


async def test_update_task_foreign_raises_not_found() -> None:
    repo = InMemoryTaskRepository()
    created = await CreateTaskUseCase(repo).execute(CreateTaskInput(owner_id=OWNER, title="t"))
    usecase = UpdateTaskUseCase(repo)
    with pytest.raises(NotFoundError):
        await usecase.execute(task_id=created.id, owner_id=OTHER, changes=TaskChanges(title="x"))


async def test_delete_task() -> None:
    repo = InMemoryTaskRepository()
    created = await CreateTaskUseCase(repo).execute(CreateTaskInput(owner_id=OWNER, title="t"))
    usecase = DeleteTaskUseCase(repo)

    await usecase.execute(task_id=created.id, owner_id=OWNER)
    assert await repo.get(created.id) is None

    # Second delete: already gone.
    with pytest.raises(NotFoundError):
        await usecase.execute(task_id=created.id, owner_id=OWNER)

    # Foreign owner cannot delete.
    other_task = await CreateTaskUseCase(repo).execute(CreateTaskInput(owner_id=OWNER, title="t2"))
    with pytest.raises(NotFoundError):
        await usecase.execute(task_id=other_task.id, owner_id=OTHER)
