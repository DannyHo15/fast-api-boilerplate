"""Unit tests for the Task domain entity."""

import uuid

import pytest

from app.domain.entities.task import Task, TaskStatus, validate_description, validate_title
from app.domain.exceptions import DomainError


def test_create_defaults() -> None:
    owner_id = uuid.uuid4()
    task = Task.create(owner_id=owner_id, title="  Buy milk  ")

    assert task.owner_id == owner_id
    assert task.title == "Buy milk"  # trimmed
    assert task.status is TaskStatus.PENDING
    assert task.description is None
    assert task.created_at is not None
    assert task.updated_at is not None


def test_create_ids_are_unique() -> None:
    owner_id = uuid.uuid4()
    a = Task.create(owner_id=owner_id, title="a")
    b = Task.create(owner_id=owner_id, title="b")
    assert a.id != b.id


@pytest.mark.parametrize(
    "title",
    ["", "   ", "x" * 256],
)
def test_validate_title_rejects_invalid(title: str) -> None:
    with pytest.raises(DomainError):
        validate_title(title)


def test_validate_description() -> None:
    assert validate_description(None) is None
    assert validate_description("  ") is None
    assert validate_description("hello") == "hello"
    with pytest.raises(DomainError):
        validate_description("x" * 2001)


def test_change_status_touches_updated_at() -> None:
    task = Task.create(owner_id=uuid.uuid4(), title="t")
    original = task.updated_at
    task.change_status(TaskStatus.DONE)
    assert task.status is TaskStatus.DONE
    assert task.updated_at >= original
