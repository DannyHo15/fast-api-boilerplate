"""Task endpoints (CRUD, scoped to the authenticated user)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, TaskRepositoryDep
from app.api.schemas.common import Page, PageMeta
from app.api.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.application.tasks.create_task import CreateTaskInput, CreateTaskUseCase
from app.application.tasks.delete_task import DeleteTaskUseCase
from app.application.tasks.get_task import GetTaskUseCase
from app.application.tasks.list_tasks import ListTasksInput, ListTasksUseCase
from app.application.tasks.update_task import TaskChanges, UpdateTaskUseCase
from app.core.config import get_settings
from app.domain.entities.task import Task, TaskStatus

router = APIRouter()

_settings = get_settings()


def _build_changes(payload: TaskUpdate) -> TaskChanges:
    """Translate the partial-update payload into `TaskChanges`.

    Only fields explicitly present in the request body are applied
    (`model_fields_set`); omitted fields stay `UNSET`.
    """
    changes = TaskChanges()
    if "title" in payload.model_fields_set and payload.title is not None:
        changes.title = payload.title
    if "description" in payload.model_fields_set:
        changes.description = payload.description  # None means "clear it"
    if "status" in payload.model_fields_set and payload.status is not None:
        changes.status = payload.status
    return changes


@router.post(
    "",
    response_model=TaskRead,
    status_code=201,
    summary="Create a task",
)
async def create_task(
    payload: TaskCreate,
    tasks: TaskRepositoryDep,
    user: CurrentUser,
) -> Task:
    usecase = CreateTaskUseCase(tasks)
    return await usecase.execute(
        CreateTaskInput(
            owner_id=user.id,
            title=payload.title,
            description=payload.description,
        )
    )


@router.get(
    "",
    response_model=Page[TaskRead],
    summary="List the authenticated user's tasks",
)
async def list_tasks(
    tasks: TaskRepositoryDep,
    user: CurrentUser,
    status_filter: Annotated[
        TaskStatus | None,
        Query(alias="status", description="Filter by task status"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_settings.max_page_size)] = _settings.default_page_size,
) -> Page[TaskRead]:
    page = await ListTasksUseCase(tasks).execute(
        ListTasksInput(
            owner_id=user.id,
            status=status_filter,
            offset=offset,
            limit=limit,
        )
    )
    return Page[TaskRead](
        items=[TaskRead.model_validate(item) for item in page.items],
        meta=PageMeta(
            total=page.total,
            offset=page.offset,
            limit=page.limit,
            has_more=page.has_more,
        ),
    )


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Get a task",
)
async def get_task(
    task_id: UUID,
    tasks: TaskRepositoryDep,
    user: CurrentUser,
) -> Task:
    usecase = GetTaskUseCase(tasks)
    return await usecase.execute(task_id=task_id, owner_id=user.id)


@router.patch(
    "/{task_id}",
    response_model=TaskRead,
    summary="Partially update a task",
)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    tasks: TaskRepositoryDep,
    user: CurrentUser,
) -> Task:
    usecase = UpdateTaskUseCase(tasks)
    return await usecase.execute(
        task_id=task_id,
        owner_id=user.id,
        changes=_build_changes(payload),
    )


@router.delete(
    "/{task_id}",
    status_code=204,
    summary="Delete a task",
)
async def delete_task(
    task_id: UUID,
    tasks: TaskRepositoryDep,
    user: CurrentUser,
) -> None:
    usecase = DeleteTaskUseCase(tasks)
    await usecase.execute(task_id=task_id, owner_id=user.id)
