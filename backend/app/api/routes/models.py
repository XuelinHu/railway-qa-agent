"""The lightweight model endpoint the chat UI needs.

Deliberately separate from ``/api/admin/models``: listing the models a member
may pick from is not an administrative act, so it is guarded by plain
authentication rather than ``model:read``. Switching is *not* offered here —
that is an administrative action and lives only under ``/api/admin/models``,
so there is exactly one write path for it.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentPrincipal, DbSession
from app.core.permissions import PERM_MODEL_SWITCH
from app.services.model_service import (
    PROVIDER_NONE,
    list_model_infos,
    resolve_active_model,
    resolve_provider,
)

router = APIRouter()


class ModelOption(BaseModel):
    name: str
    is_active: bool = False
    loaded: bool = False
    parameter_size: str | None = None
    quantization: str | None = None
    size_label: str = ""


class ModelOptionsResponse(BaseModel):
    active_model: str | None = None
    provider: str = PROVIDER_NONE
    available: bool = False
    can_switch: bool = False
    models: list[ModelOption] = Field(default_factory=list)


@router.get("", response_model=ModelOptionsResponse)
async def list_options(
    db: DbSession,
    principal: CurrentPrincipal,
) -> ModelOptionsResponse:
    payload = await list_model_infos(db)
    active = payload.active_model or await resolve_active_model(db)
    return ModelOptionsResponse(
        active_model=active,
        provider=payload.provider or await resolve_provider(db),
        available=payload.ollama_online,
        can_switch=principal.has(PERM_MODEL_SWITCH),
        models=[
            ModelOption(
                name=model.name,
                is_active=model.name == active,
                loaded=model.loaded,
                parameter_size=model.parameter_size,
                quantization=model.quantization,
                size_label=model.size_label,
            )
            for model in payload.models
        ],
    )
