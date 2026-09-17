"""Retrieval-augmented question answering.

The flow is split into steps — :meth:`ChatService.prepare`,
:meth:`ChatService.retrieve`, :meth:`ChatService.build_messages` and
:meth:`ChatService.persist_answer` — so the streaming endpoint can run the
first two inside the request scope and the last one in a database session of
its own. See ``app/api/routes/agent.py`` for why that separation is necessary.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession, RetrievalTrace
from app.rag.retriever import RailwayRetriever
from app.rag.types import RetrievalHit
from app.schemas import ChatRequest, ChatResponse, Citation
from app.services.language import detect_language
from app.services.llm_client import LLMClient, LLMUnavailable

SYSTEM_PROMPT = (
    "You are a bilingual railway support assistant. Answer only from the provided "
    "railway regulations and terminology context. If context is insufficient, say so."
)

#: How many earlier turns are replayed so a follow-up question has a referent.
HISTORY_TURNS = 12


@dataclass
class PreparedChat:
    """Everything a later step needs, as plain values.

    Deliberately not holding ORM instances: the streaming endpoint persists the
    answer from a different database session than the one that prepared it, and
    an attached object would raise once its own session closed.
    """

    session_id: uuid.UUID
    language: str
    question: str
    user_message_id: uuid.UUID
    history: list[dict[str, str]] = field(default_factory=list)


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # Passing the session through means the administrator's model choice in
        # system_settings is honoured; a client built without it would fall back
        # to the environment and answer with a model nobody selected.
        self.llm = LLMClient(db)

    # -- steps -------------------------------------------------------------

    async def prepare(
        self,
        request: ChatRequest,
        *,
        user_id: uuid.UUID | None = None,
    ) -> PreparedChat:
        """Resolve the session, record the question and commit.

        The caller's identity comes from the authenticated principal rather than
        the payload: a request must not be able to append to somebody else's
        conversation by naming it.
        """
        language = (
            request.language
            if request.language and request.language != "auto"
            else detect_language(request.message)
        )
        session = await self._resolve_session(request, language, user_id=user_id)
        history = await self._history(session.id)

        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message,
            language=language,
        )
        self.db.add(user_message)
        # ChatSession.updated_at only advances on an UPDATE of its own row, and
        # appending a message does not touch it. Without this the conversation
        # list would not move a session to the top when it is continued, and the
        # list is ordered by that column.
        session.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(user_message)

        return PreparedChat(
            session_id=session.id,
            language=language,
            question=request.message,
            user_message_id=user_message.id,
            history=history,
        )

    async def retrieve(self, question: str) -> list[RetrievalHit]:
        return await RailwayRetriever(self.db).retrieve(question)

    def build_messages(
        self, prepared: PreparedChat, hits: list[RetrievalHit]
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(prepared.history)
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Question:\n{prepared.question}\n\n"
                    f"Context:\n{_context(hits) or '(no retrieved context)'}"
                ),
            }
        )
        return messages

    async def persist_answer(
        self,
        prepared: PreparedChat,
        answer: str,
        hits: list[RetrievalHit],
        *,
        thinking: str | None = None,
    ) -> ChatMessage:
        """Store the answer alongside its retrieval trace, then commit."""
        metadata: dict = {"retrieval_hit_count": len(hits)}
        if thinking:
            metadata["thinking"] = thinking

        assistant_message = ChatMessage(
            session_id=prepared.session_id,
            role="assistant",
            content=answer,
            language=prepared.language,
            message_metadata=metadata,
        )
        self.db.add(assistant_message)
        await self.db.flush()

        self.db.add(
            RetrievalTrace(
                message_id=assistant_message.id,
                query=prepared.question,
                hits=[hit.as_dict() for hit in hits],
            )
        )
        await self.db.commit()
        await self.db.refresh(assistant_message)
        return assistant_message

    # -- non-streaming entry point -----------------------------------------

    async def handle(
        self, request: ChatRequest, *, user_id: uuid.UUID | None = None
    ) -> ChatResponse:
        prepared = await self.prepare(request, user_id=user_id)
        hits = await self.retrieve(prepared.question)

        answer: str | None = None
        try:
            answer = await self.llm.complete(self.build_messages(prepared, hits))
        except LLMUnavailable:
            answer = None
        except Exception:  # noqa: BLE001 - degrade rather than fail the request
            answer = None

        if not answer:
            answer = self.degraded_answer(prepared.language, hits)

        assistant_message = await self.persist_answer(prepared, answer, hits)

        return ChatResponse(
            session_id=prepared.session_id,
            message_id=assistant_message.id,
            answer=answer,
            language=prepared.language,
            citations=[Citation(**hit.as_dict()) for hit in hits],
        )

    # -- helpers -----------------------------------------------------------

    async def _resolve_session(
        self,
        request: ChatRequest,
        language: str,
        *,
        user_id: uuid.UUID | None,
    ) -> ChatSession:
        if request.session_id:
            session = await self.db.get(ChatSession, request.session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="会话不存在")
            if session.user_id is not None and session.user_id != user_id:
                # Deliberately the same response as a missing session: whether
                # somebody else's conversation exists is not the caller's
                # business.
                raise HTTPException(status_code=404, detail="会话不存在")
            if session.user_id is None and user_id is not None:
                # Claim a pre-authentication conversation on first use.
                session.user_id = user_id
            return session

        title = request.message.strip().replace("\n", " ")[:80] or "新会话"
        session = ChatSession(user_id=user_id, title=title, language=language)
        self.db.add(session)
        await self.db.flush()
        return session

    async def _history(self, session_id: uuid.UUID, *, limit: int = HISTORY_TURNS):
        """Recent turns, oldest first, so follow-up questions have a referent."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role.in_(("user", "assistant")),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.content
        ]

    @staticmethod
    def degraded_answer(language: str, hits: list[RetrievalHit]) -> str:
        """The answer shown when no model is reachable.

        Retrieval is still useful on its own, so the passages are surfaced and
        the missing model is stated plainly rather than papered over.
        """
        if language == "zh":
            if hits:
                return (
                    f"已找到相关铁路术语或知识片段：\n{_context(hits)}\n\n"
                    "当前没有可用的大模型，暂不能生成完整的规章解释。"
                )
            return (
                "问题已保存，但知识库中没有检索到相关内容，且当前没有可用的大模型，"
                "因此暂时无法给出可靠的规章答案。"
            )

        if hits:
            return (
                f"Relevant railway terminology or knowledge snippets were found:\n"
                f"{_context(hits)}\n\n"
                "No language model is available, so a full regulatory answer "
                "cannot be generated."
            )
        return (
            "Your question has been saved, but nothing relevant was found in the "
            "knowledge base and no language model is available, so a reliable "
            "answer cannot be given."
        )


def _context(hits: list[RetrievalHit]) -> str:
    return "\n".join(f"- {hit.text}" for hit in hits)
