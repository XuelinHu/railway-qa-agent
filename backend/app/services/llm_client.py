from __future__ import annotations

import httpx

from app.core.config import settings


class LLMClient:
    async def complete(self, messages: list[dict[str, str]]) -> str | None:
        if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
            return None

        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": settings.llm_temperature,
        }

        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]
