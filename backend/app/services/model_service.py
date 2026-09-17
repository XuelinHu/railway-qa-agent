"""Resolve, inspect and switch the active chat model.

Two rules shape this module:

* The active model is a runtime setting, so it lives in ``system_settings`` and
  takes precedence over ``LLM_MODEL`` from the environment.
* The GPU is shared with other workloads on this host. A model that this
  application did not load is never unloaded by this application, so every
  load/unload is recorded in ``model_events`` and provenance is reconstructed
  from that history.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import ModelEvent
from app.schemas.admin import ModelInfo, ModelListResponse
from app.services.ollama_client import (
    OllamaClient,
    OllamaError,
    human_size,
    parse_modified_at,
)
from app.services.settings_service import (
    KEY_LLM_ACTIVE_MODEL,
    KEY_LLM_PROVIDER,
    SettingsService,
)

PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI = "openai_compatible"
PROVIDER_NONE = "none"


def _looks_like_ollama(base_url: str | None) -> bool:
    return bool(base_url) and ":11434" in (base_url or "")


async def resolve_provider(db: AsyncSession | None = None) -> str:
    """Which wire protocol to speak, honouring the stored setting first."""
    configured = settings.llm_provider
    if db is not None:
        stored = await SettingsService(db).get(KEY_LLM_PROVIDER)
        if isinstance(stored, str) and stored:
            configured = stored

    if configured == "ollama":
        return PROVIDER_OLLAMA
    if configured in {"openai", PROVIDER_OPENAI}:
        return PROVIDER_OPENAI if settings.llm_api_key else PROVIDER_NONE
    # auto
    if _looks_like_ollama(settings.llm_base_url):
        return PROVIDER_OLLAMA
    if settings.llm_api_key and settings.llm_base_url:
        return PROVIDER_OPENAI
    if await OllamaClient().is_online():
        return PROVIDER_OLLAMA
    return PROVIDER_NONE


async def resolve_active_model(db: AsyncSession | None = None) -> str | None:
    if db is not None:
        stored = await SettingsService(db).get(KEY_LLM_ACTIVE_MODEL)
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
    return (settings.llm_model or "").strip() or None


async def loaded_by_app(db: AsyncSession) -> set[str]:
    """Models whose most recent recorded lifecycle event was a load."""
    result = await db.execute(
        select(ModelEvent.model, ModelEvent.action).order_by(
            ModelEvent.created_at.asc(), ModelEvent.id.asc()
        )
    )
    state: dict[str, str] = {}
    for model, action in result.all():
        state[model] = action
    return {model for model, action in state.items() if action == "load"}


async def record_event(
    db: AsyncSession,
    *,
    model: str,
    action: str,
    size_vram: int | None = None,
    actor_id: Any = None,
    detail: dict | None = None,
) -> None:
    db.add(
        ModelEvent(
            model=model,
            action=action,
            size_vram=size_vram,
            actor_id=actor_id,
            detail=detail,
        )
    )
    await db.commit()


def _to_info(
    *,
    name: str,
    tag: dict | None = None,
    running: dict | None = None,
    active: str | None = None,
    loaded_by_app: bool = False,
) -> ModelInfo:
    tag = tag or {}
    running = running or {}
    details = tag.get("details") or running.get("details") or {}
    size = int(tag.get("size") or running.get("size") or 0)
    return ModelInfo(
        name=name,
        size=size,
        size_label=human_size(size),
        family=details.get("family"),
        parameter_size=details.get("parameter_size"),
        quantization=details.get("quantization_level"),
        modified_at=parse_modified_at(tag.get("modified_at")),
        context_length=_context_length(tag.get("model_info")),
        loaded=bool(running),
        size_vram=int(running.get("size_vram") or 0),
        expires_at=parse_modified_at(running.get("expires_at")),
        is_active=name == active,
        loaded_by_app=loaded_by_app,
    )


def _context_length(model_info: dict | None) -> int | None:
    for key, value in (model_info or {}).items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return None


async def list_model_infos(
    db: AsyncSession,
    *,
    client: OllamaClient | None = None,
) -> ModelListResponse:
    client = client or OllamaClient()
    active = await resolve_active_model(db)
    provider = await resolve_provider(db)

    try:
        tags = await client.list_models()
        running = await client.running_models()
    except OllamaError as exc:
        return ModelListResponse(
            active_model=active,
            provider=provider,
            ollama_online=False,
            gpu_note=str(exc),
        )

    by_app = await loaded_by_app(db)
    running_by_name = {item.get("name") or item.get("model"): item for item in running}

    infos: list[ModelInfo] = []
    for tag in tags:
        name = tag.get("name") or tag.get("model") or ""
        if not name:
            continue
        infos.append(
            _to_info(
                name=name,
                tag=tag,
                running=running_by_name.get(name),
                active=active,
                loaded_by_app=name in by_app,
            )
        )

    # A model can be resident without appearing in /api/tags only if it was
    # deleted mid-flight; surfacing it keeps the VRAM panel honest.
    known = {info.name for info in infos}
    for name, item in running_by_name.items():
        if name and name not in known:
            infos.append(
                _to_info(
                    name=name,
                    running=item,
                    active=active,
                    loaded_by_app=name in by_app,
                )
            )

    infos.sort(key=lambda info: (not info.loaded, not info.is_active, info.name))

    return ModelListResponse(
        active_model=active,
        provider=provider,
        ollama_online=True,
        ollama_version=await client.version(),
        gpu_note=await _gpu_note(running),
        models=infos,
    )


async def _gpu_note(running: list[dict]) -> str | None:
    total = sum(int(item.get("size_vram") or 0) for item in running)
    if not total:
        return None
    return f"当前已加载 {len(running)} 个模型，共占用显存 {human_size(total)}"
