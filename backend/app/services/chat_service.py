from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession, RetrievalTrace
from app.rag.retriever import RailwayRetriever
from app.schemas import ChatRequest, ChatResponse, Citation
from app.services.language import detect_language
from app.services.llm_client import LLMClient


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = LLMClient()

    async def handle(self, request: ChatRequest) -> ChatResponse:
        language = (
            request.language
            if request.language and request.language != "auto"
            else detect_language(request.message)
        )
        session = await self._get_or_create_session(request, language)

        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=request.message,
            language=language,
        )
        self.db.add(user_message)
        await self.db.flush()

        hits = await RailwayRetriever(self.db).retrieve(request.message)
        answer = await self._generate_answer(request.message, language, hits)

        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            language=language,
            message_metadata={"retrieval_hit_count": len(hits)},
        )
        self.db.add(assistant_message)
        await self.db.flush()

        self.db.add(
            RetrievalTrace(
                message_id=assistant_message.id,
                query=request.message,
                hits=[hit.as_dict() for hit in hits],
            )
        )

        await self.db.commit()
        await self.db.refresh(assistant_message)

        citations = [Citation(**hit.as_dict()) for hit in hits]
        return ChatResponse(
            session_id=session.id,
            message_id=assistant_message.id,
            answer=answer,
            language=language,
            citations=citations,
        )

    async def _get_or_create_session(self, request: ChatRequest, language: str) -> ChatSession:
        if request.session_id:
            session = await self.db.get(ChatSession, request.session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Chat session not found")
            return session

        title = request.message.strip().replace("\n", " ")[:80] or "New conversation"
        session = ChatSession(user_id=request.user_id, title=title, language=language)
        self.db.add(session)
        await self.db.flush()
        return session

    async def _generate_answer(self, question: str, language: str, hits: list) -> str:
        context = "\n".join(f"- {hit.text}" for hit in hits)
        system_prompt = (
            "You are a bilingual railway support assistant. Answer only from the provided "
            "railway regulations and terminology context. If context is insufficient, say so."
        )
        user_prompt = f"Question:\n{question}\n\nContext:\n{context or '(no retrieved context)'}"

        try:
            llm_answer = await self.llm.complete(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception:
            llm_answer = None

        if llm_answer:
            return llm_answer

        if language == "zh":
            if hits:
                joined = "\n".join(f"- {hit.text}" for hit in hits)
                return (
                    f"已找到相关铁路术语或知识片段：\n{joined}\n\n"
                    "当前未配置 LLM，暂不能生成完整规章解释。"
                )
            return (
                "问题已保存。当前后端对话与检索接口已可用，"
                "但尚未完成知识库向量入库或 LLM 配置，所以暂不能给出可靠的规章答案。"
            )

        if hits:
            joined = "\n".join(f"- {hit.text}" for hit in hits)
            return (
                f"Relevant railway terminology or knowledge snippets were found:\n{joined}\n\n"
                "LLM generation is not configured yet, "
                "so a full regulatory answer is not available."
            )
        return (
            "Your question has been saved. The chat and retrieval API is available, "
            "but vector ingestion or LLM configuration is not complete yet, "
            "so I cannot provide a reliable regulatory answer."
        )
