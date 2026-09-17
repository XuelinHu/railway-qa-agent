"""Administration console: overview statistics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, require_permission
from app.core.permissions import PERM_DASHBOARD_READ
from app.models import (
    ChatMessage,
    ChatSession,
    PasswordResetRequest,
    Role,
    TerminologyEntry,
    User,
)
from app.schemas.admin import DashboardStats
from app.services.model_service import list_model_infos, resolve_active_model, resolve_provider

router = APIRouter()


async def _count(db: AsyncSession, entity, *where) -> int:
    return int(await db.scalar(select(func.count()).select_from(entity).where(*where)) or 0)


@router.get("/stats", response_model=DashboardStats)
async def stats(
    db: DbSession,
    _: Annotated[object, Depends(require_permission(PERM_DASHBOARD_READ))],
) -> DashboardStats:
    now = datetime.now(UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    payload = DashboardStats(
        users_total=await _count(db, User),
        users_active=await _count(db, User, User.is_active.is_(True)),
        users_new_7d=await _count(db, User, User.created_at >= now - timedelta(days=7)),
        sessions_total=await _count(db, ChatSession),
        sessions_today=await _count(db, ChatSession, ChatSession.created_at >= start_of_today),
        messages_total=await _count(db, ChatMessage),
        terminology_total=await _count(db, TerminologyEntry),
        roles_total=await _count(db, Role),
        pending_reset_requests=await _count(
            db, PasswordResetRequest, PasswordResetRequest.status == "pending"
        ),
        model_name=await resolve_active_model(db),
        model_provider=await resolve_provider(db),
    )

    # Live GPU state is decoration on this page: if Ollama is down the counts
    # above are still worth returning, so a failure here only clears the badges.
    models = await list_model_infos(db)
    payload.ollama_online = models.ollama_online
    payload.ollama_models = len(models.models)

    return payload
