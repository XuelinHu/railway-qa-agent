"""The original synchronous chat API, kept working and now correctly scoped.

``POST /api/chat`` still accepts anonymous callers so the pre-authentication
prototype keeps working, but a conversation list is always scoped to the caller:
an anonymous caller sees only the conversations they started in this browser
(none, since they carry no identity), and an authenticated one sees only their
own. Everything a member can see about other people's conversations is behind
the administration console.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import OptionalPrincipal
from app.db.session import get_db
from app.models import ChatMessage, ChatSession, RetrievalTrace
from app.schemas import ChatMessageRead, ChatRequest, ChatResponse, ChatSessionRead, Citation
from app.services.chat_service import ChatService

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: DbSession,
    principal: OptionalPrincipal,
) -> ChatResponse:
    return await ChatService(db).handle(request, user_id=_actor_id(principal))


@router.get("/sessions", response_model=list[ChatSessionRead])
async def list_sessions(
    db: DbSession,
    principal: OptionalPrincipal,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ChatSession]:
    """The caller's own conversations, most recently active first.

    An anonymous caller owns nothing, so this returns an empty list rather than
    every conversation in the database.
    """
    if principal is None:
        return []

    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == principal.user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/sessions/{session_id}", response_model=list[ChatMessageRead])
async def get_session_messages(
    session_id: UUID,
    db: DbSession,
    principal: OptionalPrincipal,
) -> list[ChatMessageRead]:
    if principal is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == principal.user.id,
        )
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    traces = await _traces(db, [message.id for message in session.messages])
    return [
        _to_read(message, traces.get(message.id)) for message in session.messages
    ]


async def _traces(
    db: AsyncSession, message_ids: list[UUID]
) -> dict[UUID, list[Citation]]:
    """Citation lists, keyed by the assistant message they belong to.

    Fetched in one query for the whole conversation: a per-message lookup would
    issue one round trip per turn.
    """
    if not message_ids:
        return {}

    result = await db.execute(
        select(RetrievalTrace).where(RetrievalTrace.message_id.in_(message_ids))
    )
    traces: dict[UUID, list[Citation]] = {}
    for trace in result.scalars().all():
        traces[trace.message_id] = [
            Citation(**hit) for hit in (trace.hits or []) if isinstance(hit, dict)
        ]
    return traces


def _to_read(message: ChatMessage, citations: list[Citation] | None) -> ChatMessageRead:
    payload = ChatMessageRead.model_validate(message, from_attributes=True)
    payload.citations = citations or []
    return payload


def _actor_id(principal) -> UUID | None:
    return principal.user.id if principal is not None else None
