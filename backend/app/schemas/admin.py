"""Schemas for the administration console."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_PATTERN,
    validate_password,
)


class UserAdminRead(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None = None
    email: str | None = None
    is_active: bool
    is_superuser: bool
    must_change_password: bool
    last_login_at: datetime | None = None
    login_count: int = 0
    created_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserAdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    is_active: bool = True
    role_codes: list[str] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.match(value):
            raise ValueError("用户名需为 3-32 位字母、数字、下划线、点或短横线")
        return value

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password(value)


class UserAdminUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    require_change: bool = True


class AssignRolesRequest(BaseModel):
    role_codes: list[str] = Field(default_factory=list)


class ResetRequestRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str | None = None
    display_name: str | None = None
    status: str
    note: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    used_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IssueResetTokenResponse(BaseModel):
    token: str
    expires_at: datetime
    message: str


class RoleRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_system: bool
    permissions: list[str] = Field(default_factory=list)
    user_count: int = 0
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class RolePermissionsUpdate(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class PermissionNode(BaseModel):
    key: str
    title: str
    perm: str | None = None
    children: list[PermissionNode] = Field(default_factory=list)


class DashboardStats(BaseModel):
    users_total: int = 0
    users_active: int = 0
    users_new_7d: int = 0
    sessions_total: int = 0
    sessions_today: int = 0
    messages_total: int = 0
    terminology_total: int = 0
    roles_total: int = 0
    pending_reset_requests: int = 0
    model_name: str | None = None
    model_provider: str | None = None
    ollama_online: bool = False
    ollama_models: int = 0


class SessionAdminRead(BaseModel):
    id: uuid.UUID
    title: str
    language: str
    user_id: uuid.UUID | None = None
    username: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    session: SessionAdminRead
    messages: list[dict] = Field(default_factory=list)


# --- terminology -----------------------------------------------------------


class TerminologyAdminRead(BaseModel):
    id: uuid.UUID
    source_term: str
    target_term: str
    source_language: str
    target_language: str
    category: str | None = None
    definition: str | None = None
    aliases: list[str] | None = None
    source_file: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TerminologyCreate(BaseModel):
    source_term: str = Field(min_length=1, max_length=300)
    target_term: str = Field(min_length=1, max_length=300)
    source_language: str = Field(default="zh", max_length=16)
    target_language: str = Field(default="en", max_length=16)
    category: str | None = Field(default=None, max_length=120)
    definition: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_file: str | None = Field(default=None, max_length=500)


class TerminologyUpdate(BaseModel):
    source_term: str | None = Field(default=None, min_length=1, max_length=300)
    target_term: str | None = Field(default=None, min_length=1, max_length=300)
    source_language: str | None = Field(default=None, max_length=16)
    target_language: str | None = Field(default=None, max_length=16)
    category: str | None = Field(default=None, max_length=120)
    definition: str | None = None
    aliases: list[str] | None = None
    source_file: str | None = Field(default=None, max_length=500)


class TerminologyImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


# --- models ----------------------------------------------------------------


class ModelInfo(BaseModel):
    name: str
    size: int = 0
    size_label: str = ""
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    modified_at: datetime | None = None
    capabilities: list[str] = Field(default_factory=list)
    context_length: int | None = None
    loaded: bool = False
    size_vram: int = 0
    expires_at: datetime | None = None
    is_active: bool = False
    loaded_by_app: bool = False


class ModelListResponse(BaseModel):
    active_model: str | None = None
    provider: str = "none"
    ollama_online: bool = False
    ollama_version: str | None = None
    gpu_note: str | None = None
    models: list[ModelInfo] = Field(default_factory=list)


class ModelActionRequest(BaseModel):
    model: str = Field(min_length=1, max_length=160)
    # Only unload models this application loaded unless explicitly overridden.
    force: bool = False


class ModelActivateRequest(BaseModel):
    model: str = Field(min_length=1, max_length=160)
    preload: bool = True
    unload_previous: bool = False


class ModelPullRequest(BaseModel):
    model: str = Field(min_length=1, max_length=160)
