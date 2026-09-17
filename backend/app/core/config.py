from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    app_name: str = "Railway QA Agent"
    app_env: str = "development"
    api_prefix: str = "/api"
    auto_create_tables: bool = True

    database_url: str = "postgresql+asyncpg://deipss:change-me@localhost:5432/railway_qa_agent"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "railway_knowledge"
    qdrant_timeout_seconds: float = 8.0

    # --- Authentication -----------------------------------------------------
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 120
    jwt_refresh_ttl_days: int = 7
    refresh_cookie_name: str = "railway_refresh"
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900

    # Bootstrap administrator, created only when the users table is empty.
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "Admin@12345"
    bootstrap_admin_display_name: str = "系统管理员"

    # --- LLM ----------------------------------------------------------------
    # `auto` routes to ollama when the base url looks like an ollama endpoint,
    # otherwise to any OpenAI-compatible chat completions service.
    llm_provider: str = "auto"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0
    # A cold 14B load can take far longer than a normal request; streaming needs
    # a generous read timeout that resets on every chunk.
    llm_stream_timeout_seconds: float = 300.0
    llm_keep_alive: str = "30m"
    llm_num_ctx: int = 8192
    llm_think: bool = False

    # --- Ollama -------------------------------------------------------------
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 30.0

    embedding_model: str = "BAAI/bge-m3"
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_timeout_seconds: float = 60.0
    embedding_batch_size: int = 16
    reranker_model: str | None = None
    rag_vector_enabled: bool = True
    retrieval_limit: int = 6

    # --- Speech -------------------------------------------------------------
    # The optional `speech` extra provides these engines. When the dependency is
    # absent the endpoints report themselves unavailable instead of crashing.
    speech_asr_enabled: bool = True
    speech_asr_model: str = "small"
    # The GPU is shared and usually full, so transcription defaults to CPU.
    speech_asr_device: str = "cpu"
    speech_asr_compute_type: str = "int8"
    speech_asr_cpu_threads: int = 4
    speech_asr_idle_unload_seconds: int = 900
    speech_tts_enabled: bool = True
    speech_tts_voice: str = "zh-CN-XiaoxiaoNeural"
    speech_tts_rate: str = "+0%"
    speech_tts_max_chars: int = 1000
    speech_cache_dir: str = "data/tts_cache"

    # --- Outbound mail (optional) ------------------------------------------
    # Without SMTP the password reset flow records a request for an
    # administrator instead of silently pretending to send mail.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    public_base_url: str = "http://127.0.0.1:4023"

    cors_origins: list[str] = [
        "http://localhost:4023",
        "http://127.0.0.1:4023",
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

    @property
    def jwt_secret_is_default(self) -> bool:
        return self.jwt_secret == DEFAULT_JWT_SECRET


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
