"""Shared application-level types (framework-free DTOs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeGuard, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    """A page of items returned by a list use case."""

    items: list[T]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + self.limit < self.total


class UnsetType:
    """Sentinel meaning 'value not provided' (distinct from `None`)."""

    _instance: UnsetType | None = None

    def __new__(cls) -> UnsetType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType()


def is_set(value: T | UnsetType) -> TypeGuard[T]:
    """Type-narrowing helper: True if `value` is a real value, not UNSET."""
    return value is not UNSET
