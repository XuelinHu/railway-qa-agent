"""Failure reporting for the model server.

An administrator reads these messages in the console, so they have to say what
actually went wrong. ``httpx.ReadTimeout`` stringifies to the empty string,
which used to surface as an error ending in a bare colon.
"""

import httpx
import pytest

from app.services.ollama_client import OllamaClient, OllamaError, OllamaUnavailable


def _client_raising(exc: Exception):
    def factory(*_args, **_kwargs) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(_raise(exc)))

    return factory


def _raise(exc: Exception):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


@pytest.mark.asyncio
async def test_timeout_is_not_reported_as_unreachable(monkeypatch):
    client = OllamaClient()
    monkeypatch.setattr(
        client, "_client", _client_raising(httpx.ReadTimeout(""))
    )

    with pytest.raises(OllamaUnavailable) as caught:
        await client.running_models()

    message = str(caught.value)
    assert "超时" in message
    # A timeout means it connected, so "无法连接" would misdirect the reader.
    assert "无法连接" not in message


@pytest.mark.asyncio
async def test_connect_failure_keeps_the_message_non_empty(monkeypatch):
    client = OllamaClient()
    monkeypatch.setattr(
        client, "_client", _client_raising(httpx.ConnectError(""))
    )

    with pytest.raises(OllamaUnavailable) as caught:
        await client.running_models()

    message = str(caught.value)
    assert "无法连接" in message
    assert not message.rstrip().endswith(":")


@pytest.mark.asyncio
async def test_error_detail_is_kept_when_ollama_reports_one(monkeypatch):
    client = OllamaClient()
    monkeypatch.setattr(
        client,
        "_client",
        lambda *a, **kw: httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(500, json={"error": "模型正在下载中"})
            )
        ),
    )

    with pytest.raises(OllamaError) as caught:
        await client.list_models()

    assert "模型正在下载中" in str(caught.value)
