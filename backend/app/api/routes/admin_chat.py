"""Administration console: conversations, messages and retrieval traces."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, client_ip, require_permission
from app.core.permissions import PERM_CHAT_DELETE, PERM_CHAT_READ
from app.db.pagination import paginate
from app.models import ChatMessage, ChatSession, RetrievalTrace, User
from app.schemas.admin import ConversationDetail, SessionAdminRead
from app.schemas.common import MessageResponse, Page, PageParams
from app.services import audit_service

router = APIRouter()

ReadChat = Annotated[object, Depends(require_permission(PERM_CHAT_READ))]
DeleteChat = Annotated[object, Depends(require_permission(PERM_CHAT_DELETE))]


async def _get_session(db: AsyncSession, session_id: uuid.UUID) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.get("/sessions", response_model=Page[SessionAdminRead])
async def list_sessions(
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    _: ReadChat,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    language: Annotated[str | None, Query(max_length=16)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> Page[SessionAdminRead]:
    stmt = select(ChatSession).join(User, User.id == ChatSession.user_id, isouter=True)
    if user_id is not None:
        stmt = stmt.where(ChatSession.user_id == user_id)
    if language:
        stmt = stmt.where(ChatSession.language == language)
    if created_from is not None:
        stmt = stmt.where(ChatSession.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(ChatSession.created_at <= created_to)

    page = await paginate(
        db,
        stmt,
        params,
        sortable={
            "created_at": ChatSession.created_at,
            "updated_at": ChatSession.updated_at,
            "title": ChatSession.title,
        },
        default_sort="updated_at",
        search_columns=(ChatSession.title, User.username, User.display_name),
    )

    counts = await _message_counts(db, [item.id for item in page.items])
    usernames = await _usernames(db, [item.user_id for item in page.items if item.user_id])

    return Page[SessionAdminRead].build(
        items=[
            _to_read(
                item,
                username=usernames.get(item.user_id),
                message_count=counts.get(item.id, 0),
            )
            for item in page.items
        ],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/sessions/{session_id}", response_model=ConversationDetail)
async def get_session(
    session_id: uuid.UUID,
    db: DbSession,
    _: ReadChat,
    params: Annotated[PageParams, Depends()],
) -> ConversationDetail:
    session = await _get_session(db, session_id)
    usernames = await _usernames(db, [session.user_id] if session.user_id else [])
    counts = await _message_counts(db, [session.id])

    page = await paginate(
        db,
        select(ChatMessage).where(ChatMessage.session_id == session_id),
        params,
        sortable={"created_at": ChatMessage.created_at},
        default_sort="created_at",
        search_columns=(ChatMessage.content,),
    )

    traces = await _traces(db, [message.id for message in page.items])

    messages: list[dict] = []
    for message in page.items:
        trace = traces.get(message.id)
        messages.append(
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "language": message.language,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "metadata": message.message_metadata,
                "trace": (
                    {
                        "query": trace.query,
                        "hits": trace.hits,
                    }
                    if trace is not None
                    else None
                ),
            }
        )

    return ConversationDetail(
        session=_to_read(
            session,
            username=usernames.get(session.user_id),
            message_count=counts.get(session.id, 0),
        ),
        messages=messages,
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: uuid.UUID,
    db: DbSession,
    actor: DeleteChat,
    request: Request,
) -> MessageResponse:
    session = await _get_session(db, session_id)
    await db.delete(session)
    await db.commit()
    await audit_service.record(
        db,
        action="chat.delete_session",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="chat_session",
        target_id=str(session_id),
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message="会话及其消息已删除")


def _to_read(
    session: ChatSession, *, username: str | None = None, message_count: int = 0
) -> SessionAdminRead:
    return SessionAdminRead(
        id=session.id,
        title=session.title,
        language=session.language,
        user_id=session.user_id,
        username=username,
        message_count=message_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def _message_counts(
    db: AsyncSession, session_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not session_ids:
        return {}
    result = await db.execute(
        select(ChatMessage.session_id, func.count())
        .where(ChatMessage.session_id.in_(session_ids))
        .group_by(ChatMessage.session_id)
    )
    return {session_id: int(count) for session_id, count in result.all()}


async def _usernames(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    unique_ids = list({user_id for user_id in user_ids if user_id})
    if not unique_ids:
        return {}
    result = await db.execute(
        select(User.id, User.username).where(User.id.in_(unique_ids))
    )
    return {user_id: username for user_id, username in result.all()}


async def _traces(
    db: AsyncSession, message_ids: list[uuid.UUID]
) -> dict[uuid.UUID, RetrievalTrace]:
    if not message_ids:
        return {}
    result = await db.execute(
        select(RetrievalTrace).where(RetrievalTrace.message_id.in_(message_ids))
    )
    return {trace.message_id: trace for trace in result.scalars().all()}
