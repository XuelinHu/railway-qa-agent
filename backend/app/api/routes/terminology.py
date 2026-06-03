from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import TerminologyEntryRead
from app.services.terminology_service import TerminologyService

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/search", response_model=list[TerminologyEntryRead])
async def search_terminology(
    db: DbSession,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TerminologyEntryRead]:
    return await TerminologyService(db).search(q, limit=limit)
