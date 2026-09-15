"""Mappers between domain entities and ORM models.

Keeping the two shapes separate means:
- the domain stays free of SQLAlchemy, and
- the database schema can evolve without touching business logic
  (and vice versa).
"""

from app.domain.entities.task import Task, TaskStatus
from app.domain.entities.user import User
from app.infrastructure.database.models.task import TaskModel
from app.infrastructure.database.models.user import UserModel


def user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        full_name=model.full_name,
        created_at=model.created_at,
    )


def task_to_domain(model: TaskModel) -> Task:
    return Task(
        id=model.id,
        owner_id=model.owner_id,
        title=model.title,
        status=TaskStatus(model.status),
        description=model.description,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def task_to_model(task: Task) -> TaskModel:
    return TaskModel(
        id=task.id,
        owner_id=task.owner_id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
