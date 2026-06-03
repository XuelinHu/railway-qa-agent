from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Railway QA Agent"
    app_env: str = "development"
    api_prefix: str = "/api"
    auto_create_tables: bool = True

    database_url: str = "postgresql+asyncpg://deipss:change-me@localhost:5432/railway_qa_agent"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "railway_knowledge"
    qdrant_timeout_seconds: float = 8.0

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0

    embedding_model: str = "BAAI/bge-m3"
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_timeout_seconds: float = 60.0
    embedding_batch_size: int = 16
    reranker_model: str | None = None
    rag_vector_enabled: bool = True
    retrieval_limit: int = 6

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str] | str:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
