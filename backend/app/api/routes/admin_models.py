"""Administration console: local model lifecycle."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, client_ip, require_permission
from app.api.sse import format_event, sse_response
from app.core.permissions import (
    PERM_MODEL_MANAGE,
    PERM_MODEL_PULL,
    PERM_MODEL_READ,
    PERM_MODEL_SWITCH,
)
from app.db.session import AsyncSessionLocal
from app.schemas.admin import (
    ModelActionRequest,
    ModelActivateRequest,
    ModelInfo,
    ModelListResponse,
    ModelPullRequest,
)
from app.schemas.common import MessageResponse
from app.services import audit_service
from app.services.model_pull import PullInProgress, PullNotFound, pull_manager
from app.services.model_service import list_model_infos, loaded_by_app, record_event
from app.services.ollama_client import OllamaClient, OllamaError
from app.services.settings_service import KEY_LLM_ACTIVE_MODEL, SettingsService

logger = logging.getLogger(__name__)

router = APIRouter()

ReadModel = Annotated[object, Depends(require_permission(PERM_MODEL_READ))]
ManageModel = Annotated[object, Depends(require_permission(PERM_MODEL_MANAGE))]
PullModel = Annotated[object, Depends(require_permission(PERM_MODEL_PULL))]
SwitchModel = Annotated[object, Depends(require_permission(PERM_MODEL_SWITCH))]


@router.get("", response_model=ModelListResponse)
async def list_models(db: DbSession, _: ReadModel) -> ModelListResponse:
    return await list_model_infos(db)


@router.get("/running", response_model=list[ModelInfo])
async def list_running(db: DbSession, _: ReadModel) -> list[ModelInfo]:
    payload = await list_model_infos(db)
    return [model for model in payload.models if model.loaded]


@router.get("/pulls", response_model=list[dict])
async def list_pulls(_: ReadModel) -> list[dict]:
    """Downloads currently in flight, so the UI can reattach after a reload."""
    return pull_manager.active()


@router.get("/pull/stream")
async def stream_pull(
    _: ReadModel,
    name: Annotated[str, Query(min_length=1, max_length=160)],
):
    """Live progress for a download.

    Deliberately a GET so the browser can consume it with ``EventSource``, which
    cannot issue a POST. It carries no side effect beyond attaching a viewer.
    """

    async def publisher():
        try:
            async for item in pull_manager.stream(name):
                yield format_event(item["event"], item["data"])
        except PullNotFound as exc:
            yield format_event("error", {"detail": str(exc)})

    return sse_response(publisher())


@router.get("/{name:path}/detail", response_model=dict)
async def model_detail(name: str, _: ReadModel) -> dict:
    try:
        return await OllamaClient().show_model(name)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/activate", response_model=ModelListResponse)
async def activate_model(
    payload: ModelActivateRequest,
    db: DbSession,
    actor: SwitchModel,
    request: Request,
) -> ModelListResponse:
    """Make a model the one chat uses, optionally warming or swapping it in."""
    client = OllamaClient()

    if payload.preload:
        previous = await loaded_by_app(db)
        try:
            await client.load_model(payload.model)
        except OllamaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        await record_event(
            db,
            model=payload.model,
            action="load",
            actor_id=actor.user.id,
            detail={"reason": "activate"},
        )

        if payload.unload_previous:
            running = _running_names(await _safe_running(client))
            for model in previous:
                # Only models this application loaded, and never the one we are
                # switching to.
                if model != payload.model and model in running:
                    await _unload(db, client, model, actor_id=actor.user.id)

    await SettingsService(db).set(
        KEY_LLM_ACTIVE_MODEL,
        payload.model,
        user_id=actor.user.id,
        description="当前问答使用的模型",
    )
    await audit_service.record(
        db,
        action="model.activate",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="model",
        target_id=payload.model,
        detail={"preload": payload.preload, "unload_previous": payload.unload_previous},
        ip_address=client_ip(request),
        commit=True,
    )
    return await list_model_infos(db)


@router.post("/load", response_model=MessageResponse)
async def load_model(
    payload: ModelActionRequest,
    db: DbSession,
    actor: ManageModel,
    request: Request,
) -> MessageResponse:
    client = OllamaClient()
    try:
        await client.load_model(payload.model)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await record_event(
        db,
        model=payload.model,
        action="load",
        actor_id=actor.user.id,
    )
    await audit_service.record(
        db,
        action="model.load",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="model",
        target_id=payload.model,
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message=f"{payload.model} 已加载到显存")


@router.post("/unload", response_model=MessageResponse)
async def unload_model(
    payload: ModelActionRequest,
    db: DbSession,
    actor: ManageModel,
    request: Request,
) -> MessageResponse:
    """Free a model's VRAM.

    The GPU is shared with other workloads, so a model this application never
    loaded is refused unless the operator explicitly forces it.
    """
    client = OllamaClient()
    running = _running_names(await _safe_running(client))
    if payload.model not in running:
        return MessageResponse(message=f"{payload.model} 当前未加载")

    if not payload.force and payload.model not in await loaded_by_app(db):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{payload.model} 不是本系统加载的，卸载可能影响其他任务；"
                "如确认要释放，请使用强制卸载"
            ),
        )

    await _unload(db, client, payload.model, actor_id=actor.user.id)
    await audit_service.record(
        db,
        action="model.unload",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="model",
        target_id=payload.model,
        detail={"force": payload.force},
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message=f"{payload.model} 已从显存卸载")


@router.post("/pull", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def pull_model(
    payload: ModelPullRequest,
    db: DbSession,
    actor: PullModel,
    request: Request,
) -> dict:
    try:
        job = await pull_manager.start(
            payload.model,
            actor_id=actor.user.id,
            session_factory=AsyncSessionLocal,
        )
    except PullInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await audit_service.record(
        db,
        action="model.pull",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="model",
        target_id=payload.model,
        ip_address=client_ip(request),
        commit=True,
    )
    return job.snapshot()


@router.delete("/{name:path}", response_model=MessageResponse)
async def delete_model(
    name: str,
    db: DbSession,
    actor: ManageModel,
    request: Request,
) -> MessageResponse:
    client = OllamaClient()
    if name in _running_names(await _safe_running(client)):
        raise HTTPException(status_code=409, detail="该模型正在显存中，请先卸载再删除")

    active = await SettingsService(db).get(KEY_LLM_ACTIVE_MODEL)
    if name == active:
        raise HTTPException(status_code=409, detail="该模型是当前使用的模型，请先切换")

    try:
        await client.delete_model(name)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    await record_event(
        db,
        model=name,
        action="delete",
        actor_id=actor.user.id,
    )
    await audit_service.record(
        db,
        action="model.delete",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="model",
        target_id=name,
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message=f"{name} 已删除")


async def _unload(
    db: AsyncSession, client: OllamaClient, model: str, *, actor_id
) -> None:
    await client.unload_model(model)
    await record_event(db, model=model, action="unload", actor_id=actor_id)


async def _safe_running(client: OllamaClient) -> list[dict]:
    try:
        return await client.running_models()
    except OllamaError:
        logger.warning("could not read the loaded model list", exc_info=True)
        return []


def _running_names(models: list[dict]) -> set[str]:
    return {item.get("name") or item.get("model") or "" for item in models}
