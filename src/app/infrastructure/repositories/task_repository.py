"""SQLAlchemy implementation of `app.domain.ports.task_repository.TaskRepository`."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.task import Task, TaskStatus
from app.domain.exceptions import NotFoundError
from app.infrastructure.database.mappers import task_to_domain, task_to_model
from app.infrastructure.database.models.task import TaskModel


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: Task) -> Task:
        model = task_to_model(task)
        self._session.add(model)
        await self._session.flush()
        return task_to_domain(model)

    async def get(self, task_id: UUID) -> Task | None:
        model = await self._session.get(TaskModel, task_id)
        return task_to_domain(model) if model is not None else None

    async def get_owned(self, task_id: UUID, owner_id: UUID) -> Task | None:
        stmt = select(TaskModel).where(
            TaskModel.id == task_id,
            TaskModel.owner_id == owner_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return task_to_domain(model) if model is not None else None

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        status: TaskStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        base = select(TaskModel).where(TaskModel.owner_id == owner_id)
        if status is not None:
            base = base.where(TaskModel.status == status.value)

        total = (
            await self._session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()

        stmt = (
            base.order_by(TaskModel.created_at.desc(), TaskModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [task_to_domain(m) for m in models], total

    async def save(self, task: Task) -> Task:
        model = await self._session.get(TaskModel, task.id)
        if model is None:
            raise NotFoundError(f"Task {task.id} not found")
        model.title = task.title
        model.description = task.description
        model.status = task.status.value
        model.updated_at = task.updated_at
        await self._session.flush()
        return task_to_domain(model)

    async def delete(self, task_id: UUID, owner_id: UUID) -> bool:
        task = await self.get_owned(task_id, owner_id)
        if task is None:
            return False
        await self._session.execute(delete(TaskModel).where(TaskModel.id == task_id))
        await self._session.flush()
        return True
