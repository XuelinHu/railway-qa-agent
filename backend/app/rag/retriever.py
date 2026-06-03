from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.rag.embedding import get_embedder
from app.rag.types import RetrievalHit
from app.rag.vector_store import QdrantVectorStore
from app.services.terminology_service import TerminologyService


class RailwayRetriever:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def retrieve(self, query: str, limit: int | None = None) -> list[RetrievalHit]:
        max_hits = limit or settings.retrieval_limit
        terms = await TerminologyService(self.db).search(query, limit=min(max_hits, 5))
        hits: list[RetrievalHit] = []

        for term in terms:
            text = f"{term.source_term} = {term.target_term}"
            if term.definition:
                text += f"; {term.definition}"
            hits.append(
                RetrievalHit(
                    text=text,
                    source_file=term.source_file,
                    score=1.0,
                    kind="terminology",
                )
            )

        if settings.rag_vector_enabled:
            hits.extend(await self._retrieve_from_qdrant(query, limit=max_hits))

        return dedupe_hits(hits)[:max_hits]

    async def _retrieve_from_qdrant(self, query: str, limit: int) -> list[RetrievalHit]:
        try:
            query_vector = get_embedder().embed_texts([query])[0]
            store = QdrantVectorStore()
            try:
                return await store.search(query_vector=query_vector, limit=limit)
            finally:
                await store.close()
        except Exception:
            return []


def dedupe_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    deduped: list[RetrievalHit] = []
    seen: set[tuple[str | None, int | None, str]] = set()
    for hit in hits:
        key = (hit.source_file, hit.chunk_index, hit.text[:120])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped
