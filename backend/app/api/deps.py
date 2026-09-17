"""Shared FastAPI dependencies: authentication and permission enforcement."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import SUPERUSER_PERMISSION
from app.core.security import ACCESS_TOKEN_TYPE, TokenError, decode_token
from app.db.session import get_db
from app.models import Role, User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False so protected routes can raise their own 401 shape and
# optional-auth routes can run anonymously.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


@dataclass(frozen=True)
class Principal:
    user: User
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_superuser(self) -> bool:
        return self.user.is_superuser or SUPERUSER_PERMISSION in self.permissions

    def has(self, *codes: str) -> bool:
        """True when the principal holds *any* of ``codes``."""
        if not codes:
            return True
        if self.is_superuser:
            return True
        return any(code in self.permissions for code in codes)


async def _load_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.role_links)
            .selectinload(UserRole.role)
            .selectinload(Role.permission_links)
        )
    )
    return result.scalar_one_or_none()


def _build_principal(user: User) -> Principal:
    roles = frozenset(link.role.code for link in user.role_links if link.role is not None)
    permissions: set[str] = set()
    for link in user.role_links:
        if link.role is None:
            continue
        permissions.update(item.permission for item in link.role.permission_links)
    if user.is_superuser:
        permissions.add(SUPERUSER_PERMISSION)
    return Principal(user=user, roles=roles, permissions=frozenset(permissions))


async def get_optional_principal(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> Principal | None:
    """Resolve the caller when a valid token is present, otherwise ``None``."""
    if credentials is None or not credentials.credentials:
        return None

    cached = getattr(request.state, "principal", None)
    if cached is not None:
        return cached

    try:
        payload = decode_token(credentials.credentials, expected_type=ACCESS_TOKEN_TYPE)
        user_id = uuid.UUID(payload["sub"])
    except (TokenError, ValueError, KeyError):
        return None

    user = await _load_user(db, user_id)
    if user is None or not user.is_active:
        return None

    principal = _build_principal(user)
    request.state.principal = principal
    return principal


async def get_current_principal(
    principal: Annotated[Principal | None, Depends(get_optional_principal)],
) -> Principal:
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
OptionalPrincipal = Annotated[Principal | None, Depends(get_optional_principal)]


def require_permission(*codes: str):
    """Dependency factory: the caller must hold at least one of ``codes``."""

    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if not principal.has(*codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有访问该功能的权限",
            )
        return principal

    return dependency


def require_superuser():
    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if not principal.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该操作仅限超级管理员",
            )
        return principal

    return dependency


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
