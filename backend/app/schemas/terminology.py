from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TerminologyEntryRead(BaseModel):
    id: UUID
    source_term: str
    target_term: str
    source_language: str
    target_language: str
    category: str | None = None
    definition: str | None = None
    aliases: list[str] | None = None
    source_file: str | None = None

    model_config = ConfigDict(from_attributes=True)

