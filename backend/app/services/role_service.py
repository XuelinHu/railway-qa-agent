"""Role and permission administration."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import SUPERUSER_PERMISSION, all_permissions
from app.models import Role, RolePermission, User, UserRole
from app.schemas.admin import RoleCreate, RoleRead, RoleUpdate

ROLE_LOAD_OPTIONS = (selectinload(Role.permission_links),)

#: Permission codes a role may hold. The superuser wildcard is accepted here
#: but granting it is separately gated on the actor being a superuser.
VALID_PERMISSIONS = frozenset(all_permissions()) | {SUPERUSER_PERMISSION}


def _validate_codes(permissions: list[str]) -> list[str]:
    unknown = sorted(set(permissions) - VALID_PERMISSIONS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知权限码: {', '.join(unknown)}")
    return sorted(set(permissions))


def to_read(role: Role, *, user_count: int = 0) -> RoleRead:
    return RoleRead(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(link.permission for link in role.permission_links),
        user_count=user_count,
        created_at=role.created_at,
    )


class RoleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def user_counts(self) -> dict[uuid.UUID, int]:
        result = await self.db.execute(
            select(UserRole.role_id, func.count()).group_by(UserRole.role_id)
        )
        return {role_id: int(count) for role_id, count in result.all()}

    async def get(self, role_id: uuid.UUID) -> Role:
        # populate_existing: see UserService.get — the session does not expire on
        # commit, so the permission collection would otherwise be the pre-write one.
        result = await self.db.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(*ROLE_LOAD_OPTIONS)
            .execution_options(populate_existing=True)
        )
        role = result.scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=404, detail="角色不存在")
        return role

    async def create(self, payload: RoleCreate, *, actor_is_superuser: bool) -> Role:
        self._guard_wildcard(payload.permissions, actor_is_superuser=actor_is_superuser)
        permissions = _validate_codes(payload.permissions)

        taken = await self.db.scalar(select(Role).where(Role.code == payload.code))
        if taken is not None:
            raise HTTPException(status_code=409, detail="该角色标识已存在")

        role = Role(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_system=False,
        )
        self.db.add(role)
        await self.db.flush()

        for permission in permissions:
            self.db.add(RolePermission(role_id=role.id, permission=permission))

        await self.db.commit()
        return await self.get(role.id)

    async def update(self, role: Role, payload: RoleUpdate) -> Role:
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            if value is not None:
                setattr(role, field, value)
        await self.db.commit()
        return await self.get(role.id)

    async def set_permissions(
        self,
        role: Role,
        permissions: list[str],
        *,
        actor_is_superuser: bool,
    ) -> Role:
        self._guard_wildcard(permissions, actor_is_superuser=actor_is_superuser)

        if role.is_system and SUPERUSER_PERMISSION in permissions:
            raise HTTPException(
                status_code=400, detail="内置角色不允许直接授予超级管理员通配权限"
            )

        wanted = set(_validate_codes(permissions))
        current = {link.permission: link for link in role.permission_links}

        for permission, link in current.items():
            if permission not in wanted:
                await self.db.delete(link)
        for permission in sorted(wanted - current.keys()):
            self.db.add(RolePermission(role_id=role.id, permission=permission))

        await self.db.commit()
        return await self.get(role.id)

    async def delete(self, role: Role) -> None:
        if role.is_system:
            raise HTTPException(status_code=400, detail="内置角色不可删除")

        holders = await self.db.scalar(
            select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)
        )
        if holders:
            raise HTTPException(
                status_code=400,
                detail=f"仍有 {int(holders)} 个用户使用该角色，请先解除关联",
            )

        await self.db.delete(role)
        await self.db.commit()

    async def superuser_count(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count()).select_from(User).where(User.is_superuser.is_(True))
            )
            or 0
        )

    @staticmethod
    def _guard_wildcard(permissions: list[str], *, actor_is_superuser: bool) -> None:
        # Without this, anyone holding role:update could grant themselves "*" and
        # escalate to full control of the console.
        if SUPERUSER_PERMISSION in permissions and not actor_is_superuser:
            raise HTTPException(status_code=403, detail="仅超级管理员可授予通配权限")
