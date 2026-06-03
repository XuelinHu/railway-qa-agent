import uuid
from collections.abc import Iterable

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.rag.docx_loader import DocumentChunk
from app.rag.types import RetrievalHit


class QdrantVectorStore:
    def __init__(self) -> None:
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            timeout=settings.qdrant_timeout_seconds,
        )
        self.collection_name = settings.qdrant_collection

    async def ensure_collection(self, vector_size: int, recreate: bool = False) -> None:
        exists = await self.client.collection_exists(self.collection_name)
        if exists and recreate:
            await self.client.delete_collection(self.collection_name)
            exists = False
        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    async def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> None:
        points = [
            PointStruct(
                id=stable_point_id(chunk.source_file, chunk.chunk_index),
                vector=vector,
                payload={
                    "text": chunk.text,
                    "source_file": chunk.source_file,
                    "heading": chunk.heading,
                    "chunk_index": chunk.chunk_index,
                    "doc_type": infer_doc_type(chunk.source_file),
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            await self.client.upsert(collection_name=self.collection_name, points=points)

    async def search(self, query_vector: list[float], limit: int) -> list[RetrievalHit]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        hits: list[RetrievalHit] = []
        for point in response.points:
            payload = point.payload or {}
            text = payload.get("text")
            if not isinstance(text, str) or not text:
                continue
            hits.append(
                RetrievalHit(
                    text=text,
                    source_file=as_optional_str(payload.get("source_file")),
                    heading=as_optional_str(payload.get("heading")),
                    chunk_index=as_optional_int(payload.get("chunk_index")),
                    score=point.score,
                    kind="document",
                )
            )
        return hits

    async def close(self) -> None:
        await self.client.close()


def batched(items: list[DocumentChunk], size: int) -> Iterable[list[DocumentChunk]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def stable_point_id(source_file: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_file}:{chunk_index}"))


def infer_doc_type(source_file: str) -> str:
    if "词汇" in source_file:
        return "terminology"
    if "规章" in source_file or "ECRL" in source_file:
        return "regulation"
    return "document"


def as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def as_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
