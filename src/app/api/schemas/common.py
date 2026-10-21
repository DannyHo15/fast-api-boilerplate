"""Shared API schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorEnvelope(BaseModel):
    """Shape of every error response in this API."""

    error: ErrorDetail


class PageMeta(BaseModel):
    total: int
    offset: int
    limit: int
    has_more: bool = Field(description="Whether more items exist beyond this page")


class Page(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    meta: PageMeta
