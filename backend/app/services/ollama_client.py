"""Thin async client for the Ollama native API.

The native API is used rather than the ``/v1`` OpenAI-compatible shim because
the shim silently drops ``keep_alive``, ``think`` and ``options.num_ctx`` — the
three knobs that matter for managing a 24GB card.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings

#: Pulling a model is a multi-gigabyte download; the read timeout must not fire
#: while a chunk is in flight.
_PULL_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)


def _inference_timeout() -> httpx.Timeout:
    """Timeout for a request that generates tokens.

    Distinct from the short default used for discovery calls: the read timeout
    applies between chunks, not to the response as a whole, so it only has to
    cover the pause before the first token. On a GPU shared with other work that
    pause can comfortably exceed the 30s a listing call should be allowed.
    """
    return httpx.Timeout(
        connect=10.0,
        read=settings.llm_stream_timeout_seconds,
        write=30.0,
        pool=10.0,
    )


class OllamaError(RuntimeError):
    """Any failure talking to Ollama."""


class OllamaUnavailable(OllamaError):
    """Ollama is not reachable at the configured base URL."""


class OllamaModelNotFound(OllamaError):
    """Ollama is reachable but does not know the requested model."""


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.ollama_timeout_seconds

    # -- plumbing ----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _client(self, timeout: httpx.Timeout | float | None = None) -> httpx.AsyncClient:
        # trust_env=False is deliberate. This process may run behind a proxy
        # (ALL_PROXY is set on the deployment host), and httpx builds the proxy
        # transports eagerly at construction — including a SOCKS one whose
        # `socksio` dependency is absent — before NO_PROXY can exempt 127.0.0.1.
        # A model server on loopback must never be routed through a proxy anyway.
        return httpx.AsyncClient(timeout=timeout or self.timeout, trust_env=False)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        try:
            async with self._client() as client:
                response = await client.request(method, self._url(path), json=payload)
        except Exception as exc:  # noqa: BLE001 - any transport failure means "unavailable"
            raise OllamaUnavailable(f"无法连接 Ollama ({self.base_url}): {exc}") from exc

        if response.status_code == 404:
            raise OllamaModelNotFound(_detail(response) or "模型不存在")
        if response.status_code >= 400:
            raise OllamaError(_detail(response) or f"Ollama 返回 {response.status_code}")
        if not response.content:
            return None
        return response.json()

    async def _stream(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout: httpx.Timeout | float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async with self._client(timeout) as client:
                async with client.stream(
                    "POST", self._url(path), json=payload
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        if response.status_code == 404:
                            raise OllamaModelNotFound(
                                _detail(response) or "模型不存在"
                            )
                        raise OllamaError(
                            _detail(response) or f"Ollama 返回 {response.status_code}"
                        )
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(chunk, dict) and chunk.get("error"):
                            raise OllamaError(str(chunk["error"]))
                        yield chunk
        except OllamaError:
            raise
        except Exception as exc:  # noqa: BLE001 - any transport failure means "unavailable"
            raise OllamaUnavailable(f"无法连接 Ollama ({self.base_url}): {exc}") from exc

    # -- discovery ---------------------------------------------------------

    async def version(self) -> str | None:
        try:
            data = await self._request("GET", "/api/version")
        except OllamaError:
            return None
        return (data or {}).get("version")

    async def is_online(self) -> bool:
        return await self.version() is not None

    async def list_models(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/tags")
        return list((data or {}).get("models") or [])

    async def running_models(self) -> list[dict[str, Any]]:
        """Models currently resident in memory, with their VRAM footprint."""
        data = await self._request("GET", "/api/ps")
        return list((data or {}).get("models") or [])

    async def show_model(self, name: str) -> dict[str, Any]:
        return await self._request("POST", "/api/show", payload={"model": name}) or {}

    # -- lifecycle ---------------------------------------------------------

    async def load_model(self, name: str, *, keep_alive: str | None = None) -> None:
        """Force a model into memory by issuing an empty generation.

        Ollama has no dedicated load endpoint; an empty prompt with a non-zero
        ``keep_alive`` is the documented way to warm a model.
        """
        keep_alive = keep_alive or settings.llm_keep_alive
        async for _ in self._stream(
            "/api/generate",
            {"model": name, "prompt": "", "stream": False, "keep_alive": keep_alive},
        ):
            pass

    async def unload_model(self, name: str) -> None:
        async for _ in self._stream(
            "/api/generate",
            {"model": name, "prompt": "", "stream": False, "keep_alive": 0},
        ):
            pass

    async def delete_model(self, name: str) -> None:
        # /api/delete takes its argument in the request body, not the query string.
        await self._request("DELETE", "/api/delete", payload={"model": name})

    async def pull_model(self, name: str) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self._stream(
            "/api/pull", {"model": name, "stream": True}, timeout=_PULL_TIMEOUT
        ):
            yield chunk

    # -- inference ---------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        stream: bool = True,
        think: bool | None = None,
        keep_alive: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "keep_alive": keep_alive or settings.llm_keep_alive,
        }
        if think is not None:
            payload["think"] = think
        if options:
            payload["options"] = options
        # Both modes generate an answer, so both get the inference timeout — a
        # non-streaming call is just as long, it simply arrives all at once.
        async for chunk in self._stream(
            "/api/chat", payload, timeout=_inference_timeout()
        ):
            yield chunk


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - any decode failure falls back to raw text
        return response.text.strip()[:300]
    if isinstance(body, dict):
        return str(body.get("error") or body.get("detail") or "").strip()[:300]
    return ""


def parse_modified_at(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def human_size(num_bytes: int | None) -> str:
    if not num_bytes:
        return "-"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"
