"""Generic pagination over SQLAlchemy select statements."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.base import ExecutableOption

from app.schemas.common import Page, PageParams


async def paginate(
    db: AsyncSession,
    stmt: Select,
    params: PageParams,
    *,
    sortable: Mapping[str, InstrumentedAttribute] | None = None,
    default_sort: str | None = None,
    search_columns: Sequence[InstrumentedAttribute] = (),
    options: Sequence[ExecutableOption] = (),
) -> Page[Any]:
    """Execute ``stmt`` with pagination, keyword search and whitelisted sorting.

    ``sortable`` maps a client-supplied sort key to a real column. Unknown keys
    fall back to ``default_sort`` rather than being interpolated into SQL, so a
    crafted ``sort`` parameter cannot reach the database.
    """
    if params.keyword and search_columns:
        pattern = f"%{params.keyword}%"
        stmt = stmt.where(or_(*(column.ilike(pattern) for column in search_columns)))

    total = await db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    )
    total = int(total or 0)

    resolved_sort = None
    if sortable:
        key = params.sort if params.sort in sortable else default_sort
        if key and key in sortable:
            resolved_sort = sortable[key]

    if resolved_sort is not None:
        stmt = stmt.order_by(
            resolved_sort.desc() if params.order == "desc" else resolved_sort.asc()
        )

    if options:
        stmt = stmt.options(*options)

    result = await db.execute(stmt.offset(params.offset).limit(params.page_size))
    items = list(result.scalars().unique().all())

    return Page.build(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
