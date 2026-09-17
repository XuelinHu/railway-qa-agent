from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

# Deliberately modest: length is the property that matters most, and an
# over-strict policy pushes users towards predictable passwords.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _validate_username(value: str) -> str:
    value = value.strip()
    if not USERNAME_PATTERN.match(value):
        raise ValueError("用户名需为 3-32 位字母、数字、下划线、点或短横线")
    return value


def validate_password(value: str) -> str:
    """Shared password policy, reused by the admin user-creation schema."""
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"密码长度不能少于 {PASSWORD_MIN_LENGTH} 位")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"密码长度不能超过 {PASSWORD_MAX_LENGTH} 位")
    if value.isdigit() or value.isalpha():
        raise ValueError("密码需同时包含字母和数字")
    return value


_validate_password = validate_password


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None

    _check_username = field_validator("username")(_validate_username)
    _check_password = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class RoleBrief(BaseModel):
    id: uuid.UUID
    code: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None = None
    email: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    must_change_password: bool = False
    last_login_at: datetime | None = None
    login_count: int = 0
    created_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    user: UserRead
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    menus: list[dict] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    menus: list[dict] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    _check_password = field_validator("new_password")(_validate_password)


class ForgotPasswordRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class ForgotPasswordResponse(BaseModel):
    message: str
    # Populated only in development when no mail server is configured, so the
    # reset flow stays usable without silently pretending an email was sent.
    dev_reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    _check_password = field_validator("new_password")(_validate_password)
