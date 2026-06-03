from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import settings


class Embedder(Protocol):
    @property
    def dimension(self) -> int | None:
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class BgeM3Embedder:
    def __init__(self, model_name: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Local BGE-M3 embedding requires sentence-transformers. "
                "For CPU-only installs, install a CPU PyTorch wheel first, then install "
                "sentence-transformers, or configure EMBEDDING_BASE_URL to use an "
                "OpenAI-compatible embedding service."
            ) from exc

        self.model_name = model_name or settings.embedding_model
        self.model = SentenceTransformer(self.model_name)
        self._dimension: int | None = None

    @property
    def dimension(self) -> int | None:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors = [embedding.tolist() for embedding in embeddings]
        self._dimension = len(vectors[0]) if vectors else self._dimension
        return vectors


class OpenAICompatibleEmbedder:
    def __init__(self) -> None:
        if not settings.embedding_base_url:
            raise RuntimeError("EMBEDDING_BASE_URL is required for remote embeddings.")
        self._dimension: int | None = None

    @property
    def dimension(self) -> int | None:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        url = settings.embedding_base_url.rstrip("/") + "/embeddings"
        headers = {}
        if settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
        payload = {"model": settings.embedding_model, "input": texts}

        with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        vectors = [
            item["embedding"]
            for item in sorted(data["data"], key=lambda item: item.get("index", 0))
        ]
        self._dimension = len(vectors[0]) if vectors else self._dimension
        return vectors


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    if settings.embedding_base_url:
        return OpenAICompatibleEmbedder()
    return BgeM3Embedder(settings.embedding_model)
