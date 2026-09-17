"""Runtime-editable system settings.

Values stored here take precedence over environment configuration, which is what
lets an administrator switch the active chat model from the UI without a restart.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting

# Well-known keys.
KEY_LLM_PROVIDER = "llm.provider"
KEY_LLM_ACTIVE_MODEL = "llm.active_model"
KEY_LLM_TEMPERATURE = "llm.temperature"
KEY_LLM_KEEP_ALIVE = "llm.keep_alive"
KEY_LLM_NUM_CTX = "llm.num_ctx"
KEY_LLM_THINK = "llm.think"
KEY_SPEECH_TTS_VOICE = "speech.tts_voice"
KEY_SPEECH_ASR_MODEL = "speech.asr_model"


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, key: str, default: Any = None) -> Any:
        row = await self.db.get(SystemSetting, key)
        if row is None or row.value is None:
            return default
        return row.value

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            return {}
        result = await self.db.execute(
            select(SystemSetting).where(SystemSetting.key.in_(keys))
        )
        return {
            row.key: row.value
            for row in result.scalars().all()
            if row.value is not None
        }

    async def set(
        self,
        key: str,
        value: Any,
        *,
        user_id: uuid.UUID | None = None,
        description: str | None = None,
        commit: bool = True,
    ) -> None:
        stmt = (
            insert(SystemSetting)
            .values(key=key, value=value, description=description, updated_by=user_id)
            .on_conflict_do_update(
                index_elements=[SystemSetting.key],
                set_={"value": value, "updated_by": user_id},
            )
        )
        await self.db.execute(stmt)
        if commit:
            await self.db.commit()

    async def all(self) -> dict[str, Any]:
        result = await self.db.execute(select(SystemSetting))
        return {row.key: row.value for row in result.scalars().all()}
