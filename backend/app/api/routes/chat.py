from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import ChatMessage, ChatSession
from app.schemas import ChatMessageRead, ChatRequest, ChatResponse, ChatSessionRead
from app.services.chat_service import ChatService

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, db: DbSession) -> ChatResponse:
    return await ChatService(db).handle(request)


@router.get("/sessions", response_model=list[ChatSessionRead])
async def list_sessions(db: DbSession) -> list[ChatSession]:
    result = await db.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50))
    return list(result.scalars().all())


@router.get("/sessions/{session_id}", response_model=list[ChatMessageRead])
async def get_session_messages(
    session_id: UUID,
    db: DbSession,
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.messages
