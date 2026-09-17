"""Streaming question answering for the agent panel.

The answer is delivered as server-sent events so the panel can render it as it
is produced::

    event: meta       {"session_id", "message_id", "language", "model"}
    event: retrieval  {"citations": [...], "count": n}
    event: thinking   {"text": "..."}          # only for reasoning models
    event: delta      {"text": "..."}          # repeated
    event: error      {"detail": "..."}        # non-fatal: see below
    event: done       {"message_id", "session_id", "partial"}

``error`` does not necessarily mean the answer was lost: any text that arrived
before it is kept, and ``done`` still follows, so the client can render a
partial answer with a warning rather than an empty bubble.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentPrincipal, DbSession
from app.api.sse import format_event, sse_response
from app.db.session import AsyncSessionLocal
from app.rag.types import RetrievalHit
from app.schemas import ChatRequest
from app.services.chat_service import ChatService, PreparedChat
from app.services.llm_client import (
    LLMClient,
    LLMSettings,
    LLMUnavailable,
    resolve_llm_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter()

#: Shown when generation fails for a reason the caller cannot act on.
GENERIC_FAILURE_ZH = "生成回答时出错，请稍后重试"

#: Displayed when no model is reachable. The retrieval results still come
#: through, so this is a warning rather than an error.
NO_MODEL_ZH = "当前没有可用的模型，请先在管理台加载并选择模型"


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    db: DbSession,
    principal: CurrentPrincipal,
):
    """Answer ``payload.message``, streaming the answer back.

    Preparation and retrieval run here, inside the request scope, because they
    are fast and their result is needed before the response body begins.
    Everything after that runs in the generator, which opens its own database
    session — see :func:`_stream`.
    """
    service = ChatService(db)
    prepared = await service.prepare(payload, user_id=principal.user.id)
    hits = await service.retrieve(prepared.question)
    messages = service.build_messages(prepared, hits)
    config = await resolve_llm_settings(db)

    return sse_response(_stream(prepared, hits, messages, config))


async def _stream(
    prepared: PreparedChat,
    hits: list[RetrievalHit],
    messages: list[dict[str, str]],
    config: LLMSettings,
) -> AsyncIterator[str]:
    """Yield the answer, then persist it.

    The request-scoped session that built ``prepared`` is already closed by the
    time the body streams — FastAPI tears dependencies down before the response
    finishes — so the answer is written from a session opened here. That is also
    why ``prepared`` carries plain values rather than ORM instances.
    """
    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    pending_thinking: list[str] = []
    error: str | None = None
    saved: uuid.UUID | None = None

    async def save(answer: str, thinking: str) -> uuid.UUID:
        """Persist once; a later call is a no-op returning the same id."""
        nonlocal saved
        if saved is not None:
            return saved
        async with AsyncSessionLocal() as session:
            message = await ChatService(session).persist_answer(
                prepared, answer, hits, thinking=thinking or None
            )
        saved = message.id
        return saved

    try:
        yield format_event(
            "meta",
            {
                "session_id": str(prepared.session_id),
                "message_id": str(prepared.user_message_id),
                "language": prepared.language,
                "model": config.model,
                "provider": config.provider,
            },
        )
        citations: list[dict[str, Any]] = [hit.as_dict() for hit in hits]
        yield format_event("retrieval", {"citations": citations, "count": len(citations)})

        if config.usable:
            client = LLMClient()
            try:
                # on_thinking is called synchronously from inside the client's
                # generator, so anything it collects can be flushed between the
                # deltas that follow it.
                async for chunk in client.stream(
                    messages, on_thinking=pending_thinking.append, config=config
                ):
                    while pending_thinking:
                        thought = pending_thinking.pop(0)
                        thinking_parts.append(thought)
                        yield format_event("thinking", {"text": thought})
                    answer_parts.append(chunk)
                    yield format_event("delta", {"text": chunk})
            except LLMUnavailable as exc:
                error = str(exc)
            except Exception:  # noqa: BLE001 - report, never break the stream
                logger.exception("streaming failed for session %s", prepared.session_id)
                error = GENERIC_FAILURE_ZH
        else:
            error = NO_MODEL_ZH

        answer = "".join(answer_parts) or ChatService.degraded_answer(
            prepared.language, hits
        )
        if not answer_parts:
            # Nothing was generated, so the retrieval-only answer is what the
            # viewer will read; send it as a delta like any other.
            yield format_event("delta", {"text": answer})
        await save(answer, "".join(thinking_parts))
    finally:
        # Runs on completion, on failure, and when the viewer closes the panel
        # mid-answer. Keeping the partial text stops the conversation from
        # showing a question that was never answered. Nothing is yielded here:
        # the generator protocol forbids it while closing.
        if saved is None and answer_parts:
            try:
                await save("".join(answer_parts), "".join(thinking_parts))
            except Exception:  # noqa: BLE001 - a disconnect is not a crash
                logger.warning("could not save a partial answer", exc_info=True)

    if error:
        yield format_event("error", {"detail": error})
    yield format_event(
        "done",
        {
            "message_id": str(saved) if saved else None,
            "session_id": str(prepared.session_id),
            "partial": bool(error) and bool(answer_parts),
        },
    )
