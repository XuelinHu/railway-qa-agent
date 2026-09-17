"""Shared response envelopes.

Every paginated admin endpoint returns the same :class:`Page` shape so the
frontend can drive all of its tables from one composable.
"""

from __future__ import annotations

import math
from typing import Annotated, Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 200


class Page(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0
    has_next: bool = False
    has_prev: bool = False

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> Page[T]:
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class MessageResponse(BaseModel):
    message: str


class PageParams:
    """Query parameters shared by every paginated endpoint."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
        keyword: Annotated[str | None, Query(max_length=200)] = None,
        sort: Annotated[str | None, Query(max_length=64)] = None,
        order: Literal["asc", "desc"] = "desc",
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.keyword = keyword.strip() if keyword and keyword.strip() else None
        self.sort = sort
        self.order = order

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
