"""Chat completion against whichever backend is configured.

Two wire protocols are supported:

* ``ollama`` — the native ``/api/chat`` endpoint. Preferred for a locally
  managed model because it honours ``keep_alive``, ``think`` and
  ``options.num_ctx``; the ``/v1`` compatibility shim silently drops all three.
* ``openai_compatible`` — ``/chat/completions``, for a hosted or self-hosted
  OpenAI-shaped API.

The active model, temperature and context size are read from
``system_settings`` first so an administrator can change them without a
restart, falling back to environment configuration.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.model_service import (
    PROVIDER_NONE,
    PROVIDER_OLLAMA,
    resolve_active_model,
    resolve_provider,
)
from app.services.ollama_client import OllamaClient, OllamaError
from app.services.settings_service import (
    KEY_LLM_KEEP_ALIVE,
    KEY_LLM_NUM_CTX,
    KEY_LLM_TEMPERATURE,
    KEY_LLM_THINK,
    SettingsService,
)

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """No usable model backend, or the backend failed."""


class LLMSettings:
    """Everything the client needs, resolved once per request."""

    def __init__(
        self,
        *,
        provider: str,
        model: str | None,
        temperature: float,
        num_ctx: int | None,
        keep_alive: str,
        think: bool,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.think = think

    @property
    def usable(self) -> bool:
        return self.provider != PROVIDER_NONE and bool(self.model)


async def resolve_llm_settings(db: AsyncSession | None) -> LLMSettings:
    stored: dict = {}
    if db is not None:
        stored = await SettingsService(db).get_many(
            [
                KEY_LLM_TEMPERATURE,
                KEY_LLM_NUM_CTX,
                KEY_LLM_KEEP_ALIVE,
                KEY_LLM_THINK,
            ]
        )

    def pick(key: str, fallback):
        value = stored.get(key)
        return fallback if value is None else value

    return LLMSettings(
        provider=await resolve_provider(db),
        model=await resolve_active_model(db),
        temperature=float(pick(KEY_LLM_TEMPERATURE, settings.llm_temperature)),
        num_ctx=int(pick(KEY_LLM_NUM_CTX, settings.llm_num_ctx)) or None,
        keep_alive=str(pick(KEY_LLM_KEEP_ALIVE, settings.llm_keep_alive)),
        think=bool(pick(KEY_LLM_THINK, settings.llm_think)),
    )


class LLMClient:
    """Completion client. ``db`` is optional so callers without a session can
    still run against environment configuration."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
    ) -> str | None:
        """Return the full answer, or ``None`` when no backend is configured.

        ``None`` is a normal state, not an error: the application has always
        degraded to a canned answer when no model is reachable, and callers
        depend on that.
        """
        if stream:
            chunks = [chunk async for chunk in self.stream(messages)]
            return "".join(chunks)

        config = await resolve_llm_settings(self.db)
        if not config.usable:
            return None

        try:
            if config.provider == PROVIDER_OLLAMA:
                return await self._ollama_complete(config, messages)
            return await self._openai_complete(config, messages)
        except (OllamaError, httpx.HTTPError) as exc:
            logger.warning("model backend failed: %s", exc)
            return None

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        on_thinking=None,
        config: LLMSettings | None = None,
    ) -> AsyncIterator[str]:
        """Yield answer text incrementally.

        Raises :class:`LLMUnavailable` rather than degrading silently: a
        streaming caller has already committed to showing a live answer, so it
        needs to know the backend is gone rather than receive an empty stream.

        ``config`` lets a caller that already resolved the settings — and whose
        database session has since closed, as in the streaming route — pass them
        in rather than have them re-resolved against the environment.
        """
        config = config or await resolve_llm_settings(self.db)
        if not config.usable:
            raise LLMUnavailable("当前没有可用的模型，请先在管理台加载并选择模型")

        if config.provider == PROVIDER_OLLAMA:
            async for chunk in self._ollama_stream(config, messages, on_thinking):
                yield chunk
            return

        yield await self._openai_complete(config, messages)

    # -- ollama ------------------------------------------------------------

    @staticmethod
    def _ollama_options(config: LLMSettings) -> dict:
        options: dict = {"temperature": config.temperature}
        if config.num_ctx:
            options["num_ctx"] = config.num_ctx
        return options

    async def _ollama_complete(
        self, config: LLMSettings, messages: list[dict[str, str]]
    ) -> str:
        client = OllamaClient()
        parts: list[str] = []
        async for chunk in client.chat(
            messages,
            model=config.model,
            stream=False,
            think=config.think,
            keep_alive=config.keep_alive,
            options=self._ollama_options(config),
        ):
            message = chunk.get("message") or {}
            if message.get("content"):
                parts.append(message["content"])
        return "".join(parts)

    async def _ollama_stream(
        self,
        config: LLMSettings,
        messages: list[dict[str, str]],
        on_thinking,
    ) -> AsyncIterator[str]:
        client = OllamaClient()
        async for chunk in client.chat(
            messages,
            model=config.model,
            stream=True,
            think=config.think,
            keep_alive=config.keep_alive,
            options=self._ollama_options(config),
        ):
            message = chunk.get("message") or {}
            thinking = message.get("thinking")
            if thinking and on_thinking is not None:
                on_thinking(thinking)
            content = message.get("content")
            if content:
                yield content

    # -- openai-compatible -------------------------------------------------

    async def _openai_complete(
        self, config: LLMSettings, messages: list[dict[str, str]]
    ) -> str:
        if not settings.llm_base_url or not settings.llm_api_key:
            raise LLMUnavailable("OpenAI 兼容接口未配置 base_url 或 api_key")

        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
            "stream": False,
        }
        async with httpx.AsyncClient(
            timeout=settings.llm_timeout_seconds, trust_env=False
        ) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise LLMUnavailable(f"模型返回了无法解析的结果: {json.dumps(data)[:200]}") from exc
