"""Administration console: terminology CRUD and bulk import."""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, client_ip, require_permission
from app.core.permissions import (
    PERM_TERMINOLOGY_CREATE,
    PERM_TERMINOLOGY_DELETE,
    PERM_TERMINOLOGY_IMPORT,
    PERM_TERMINOLOGY_READ,
    PERM_TERMINOLOGY_UPDATE,
)
from app.db.pagination import paginate
from app.models import TerminologyEntry
from app.schemas.admin import (
    TerminologyAdminRead,
    TerminologyCreate,
    TerminologyImportResult,
    TerminologyUpdate,
)
from app.schemas.common import MessageResponse, Page, PageParams
from app.services import audit_service

router = APIRouter()

ReadTerm = Annotated[object, Depends(require_permission(PERM_TERMINOLOGY_READ))]
CreateTerm = Annotated[object, Depends(require_permission(PERM_TERMINOLOGY_CREATE))]
UpdateTerm = Annotated[object, Depends(require_permission(PERM_TERMINOLOGY_UPDATE))]
DeleteTerm = Annotated[object, Depends(require_permission(PERM_TERMINOLOGY_DELETE))]
ImportTerm = Annotated[object, Depends(require_permission(PERM_TERMINOLOGY_IMPORT))]

#: A single import request is bounded so one upload cannot hold a worker for minutes.
MAX_IMPORT_ROWS = 5000

CSV_COLUMNS = (
    "source_term",
    "target_term",
    "source_language",
    "target_language",
    "category",
    "definition",
    "aliases",
    "source_file",
)


def _to_read(entry: TerminologyEntry) -> TerminologyAdminRead:
    return TerminologyAdminRead(
        id=entry.id,
        source_term=entry.source_term,
        target_term=entry.target_term,
        source_language=entry.source_language,
        target_language=entry.target_language,
        category=entry.category,
        definition=entry.definition,
        aliases=entry.aliases,
        source_file=entry.source_file,
        created_at=entry.created_at,
    )


async def _get_entry(db: AsyncSession, entry_id: uuid.UUID) -> TerminologyEntry:
    entry = await db.get(TerminologyEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="术语不存在")
    return entry


@router.get("", response_model=Page[TerminologyAdminRead])
async def list_terminology(
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    _: ReadTerm,
    category: Annotated[str | None, Query(max_length=120)] = None,
    source_language: Annotated[str | None, Query(max_length=16)] = None,
) -> Page[TerminologyAdminRead]:
    stmt = select(TerminologyEntry)
    if category:
        stmt = stmt.where(TerminologyEntry.category == category)
    if source_language:
        stmt = stmt.where(TerminologyEntry.source_language == source_language)

    page = await paginate(
        db,
        stmt,
        params,
        sortable={
            "created_at": TerminologyEntry.created_at,
            "source_term": TerminologyEntry.source_term,
            "target_term": TerminologyEntry.target_term,
            "category": TerminologyEntry.category,
        },
        default_sort="created_at",
        search_columns=(
            TerminologyEntry.source_term,
            TerminologyEntry.target_term,
            TerminologyEntry.category,
            TerminologyEntry.definition,
        ),
    )
    return Page[TerminologyAdminRead].build(
        items=[_to_read(entry) for entry in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/categories", response_model=list[str])
async def list_categories(db: DbSession, _: ReadTerm) -> list[str]:
    result = await db.execute(
        select(TerminologyEntry.category)
        .where(TerminologyEntry.category.is_not(None))
        .distinct()
        .order_by(TerminologyEntry.category)
    )
    return [row for row in result.scalars().all() if row]


@router.get("/{entry_id}", response_model=TerminologyAdminRead)
async def get_terminology(entry_id: uuid.UUID, db: DbSession, _: ReadTerm) -> TerminologyAdminRead:
    return _to_read(await _get_entry(db, entry_id))


@router.post("", response_model=TerminologyAdminRead, status_code=status.HTTP_201_CREATED)
async def create_terminology(
    payload: TerminologyCreate,
    db: DbSession,
    actor: CreateTerm,
    request: Request,
) -> TerminologyAdminRead:
    entry = TerminologyEntry(**payload.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await audit_service.record(
        db,
        action="terminology.create",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="terminology",
        target_id=str(entry.id),
        detail={"source_term": entry.source_term},
        ip_address=client_ip(request),
        commit=True,
    )
    return _to_read(entry)


@router.patch("/{entry_id}", response_model=TerminologyAdminRead)
async def update_terminology(
    entry_id: uuid.UUID,
    payload: TerminologyUpdate,
    db: DbSession,
    actor: UpdateTerm,
    request: Request,
) -> TerminologyAdminRead:
    entry = await _get_entry(db, entry_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(entry, field, value)
    await db.commit()
    await db.refresh(entry)
    await audit_service.record(
        db,
        action="terminology.update",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="terminology",
        target_id=str(entry_id),
        detail=changes,
        ip_address=client_ip(request),
        commit=True,
    )
    return _to_read(entry)


@router.delete("/{entry_id}", response_model=MessageResponse)
async def delete_terminology(
    entry_id: uuid.UUID,
    db: DbSession,
    actor: DeleteTerm,
    request: Request,
) -> MessageResponse:
    entry = await _get_entry(db, entry_id)
    await db.delete(entry)
    await db.commit()
    await audit_service.record(
        db,
        action="terminology.delete",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="terminology",
        target_id=str(entry_id),
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message="术语已删除")


@router.post("/import", response_model=TerminologyImportResult)
async def import_terminology(
    db: DbSession,
    actor: ImportTerm,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> TerminologyImportResult:
    """Bulk upsert from a ``.json`` array or a ``.csv`` with the documented header.

    Existing ``(source_term, target_term, language pair)`` rows are updated in
    place rather than duplicated, so re-importing a corrected file is safe.
    """
    raw = await file.read()
    try:
        rows = _parse_import(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = TerminologyImportResult()
    if len(rows) > MAX_IMPORT_ROWS:
        result.errors.append(
            f"单次最多导入 {MAX_IMPORT_ROWS} 条，本次收到 {len(rows)} 条，已截断"
        )
        rows = rows[:MAX_IMPORT_ROWS]

    existing = await _existing_index(db, rows)
    for index, row in enumerate(rows, start=1):
        try:
            payload = TerminologyCreate(**row)
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator as a row error
            result.skipped += 1
            if len(result.errors) < 20:
                result.errors.append(f"第 {index} 行: {exc}")
            continue

        key = _key(payload)
        found = existing.get(key)
        if found is None:
            entry = TerminologyEntry(**payload.model_dump())
            db.add(entry)
            await db.flush()
            existing[key] = entry
            result.created += 1
        elif _apply_update(found, payload):
            result.updated += 1
        else:
            result.skipped += 1

    await db.commit()
    await audit_service.record(
        db,
        action="terminology.import",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="terminology",
        detail={
            "created": result.created,
            "updated": result.updated,
            "skipped": result.skipped,
            "filename": file.filename,
        },
        ip_address=client_ip(request),
        commit=True,
    )
    return result


_IDENTITY_FIELDS = frozenset(
    {"source_term", "target_term", "source_language", "target_language"}
)


def _key(payload: TerminologyCreate) -> tuple[str, str, str, str]:
    return (
        payload.source_term.strip().lower(),
        payload.target_term.strip().lower(),
        payload.source_language,
        payload.target_language,
    )


def _apply_update(entry: TerminologyEntry, payload: TerminologyCreate) -> bool:
    """Merge the descriptive fields of ``payload`` onto ``entry``.

    Identity fields (the two terms and the language pair) are the lookup key and
    are never rewritten. Returns whether anything actually changed.
    """
    changed = False
    for field, value in payload.model_dump().items():
        if field in _IDENTITY_FIELDS or value in (None, "", []):
            continue
        if getattr(entry, field) != value:
            setattr(entry, field, value)
            changed = True
    return changed


async def _existing_index(
    db: AsyncSession, rows: list[dict[str, Any]]
) -> dict[tuple[str, str, str, str], TerminologyEntry]:
    """Look up only the entries this import could collide with."""
    terms = {
        str(row.get("source_term") or "").strip()
        for row in rows
        if str(row.get("source_term") or "").strip()
    }
    if not terms:
        return {}

    result = await db.execute(
        select(TerminologyEntry).where(
            func.lower(TerminologyEntry.source_term).in_([term.lower() for term in terms])
        )
    )
    index: dict[tuple[str, str, str, str], TerminologyEntry] = {}
    for entry in result.scalars().all():
        index[
            (
                entry.source_term.strip().lower(),
                entry.target_term.strip().lower(),
                entry.source_language,
                entry.target_language,
            )
        ] = entry
    return index


def _parse_import(raw: bytes) -> list[dict[str, Any]]:
    text = raw.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise ValueError("文件内容为空")

    # Sniff the payload rather than trusting the extension: operators routinely
    # export JSON with a .txt or .csv name.
    if text[0] in "[{":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc
        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or [data]
        if not isinstance(data, list):
            raise ValueError("JSON 顶层需为数组，或包含 items 数组的对象")
        return [row for row in data if isinstance(row, dict)]

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")
    missing = {"source_term", "target_term"} - set(reader.fieldnames)
    if missing:
        raise ValueError(f"CSV 缺少必需列: {', '.join(sorted(missing))}")

    rows: list[dict[str, Any]] = []
    for raw_row in reader:
        row = {key: (value or "").strip() for key, value in raw_row.items() if key}
        aliases = row.get("aliases") or ""
        rows.append(
            {
                "source_term": row.get("source_term"),
                "target_term": row.get("target_term"),
                "source_language": row.get("source_language") or "zh",
                "target_language": row.get("target_language") or "en",
                "category": row.get("category") or None,
                "definition": row.get("definition") or None,
                "aliases": [
                    part.strip()
                    for part in aliases.replace(";", "|").split("|")
                    if part.strip()
                ],
                "source_file": row.get("source_file") or None,
            }
        )
    return rows
