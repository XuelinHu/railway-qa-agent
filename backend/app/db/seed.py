"""Idempotent bootstrap of roles and the first administrator.

Runs on every startup. It only ever adds what is missing, so it is safe to call
against a database that already has data.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.permissions import (
    PERM_TERMINOLOGY_READ,
    SUPERUSER_PERMISSION,
)
from app.core.security import hash_password
from app.models import Role, RolePermission, User, UserRole

logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_USER = "user"

# A member's own chat history is served by /api/chat/sessions, which is scoped
# to the caller. The admin console endpoints behind chat:read or model:read
# expose *everyone's* data, so they are deliberately not granted here — an
# administrator extends a role through the role editor instead.
DEFAULT_USER_PERMISSIONS: tuple[str, ...] = (PERM_TERMINOLOGY_READ,)


async def _upsert_role(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    description: str,
    permissions: list[str],
    is_system: bool,
) -> Role:
    result = await db.execute(
        select(Role).where(Role.code == code).options(selectinload(Role.permission_links))
    )
    role = result.scalar_one_or_none()

    if role is None:
        role = Role(code=code, name=name, description=description, is_system=is_system)
        db.add(role)
        await db.flush()
        logger.info("seeded role %s", code)
        # A freshly added instance has no loaded collection; touching
        # `role.permission_links` here would trigger a lazy load outside the
        # greenlet context and raise MissingGreenlet.
        current: dict[str, RolePermission] = {}
    else:
        current = {link.permission: link for link in role.permission_links}

    wanted = set(permissions)

    # Built-in roles are defined in code, so seeding reconciles them exactly —
    # a permission removed from the definition is revoked on next startup.
    # Custom roles are left untouched.
    if is_system:
        for permission, link in current.items():
            if permission not in wanted:
                await db.delete(link)
                logger.info("revoked %s from system role %s", permission, code)

    for permission in sorted(wanted):
        if permission not in current:
            db.add(RolePermission(role_id=role.id, permission=permission))

    return role


async def seed_rbac(db: AsyncSession) -> None:
    """Create the built-in roles and, on an empty database, the first admin."""
    await _upsert_role(
        db,
        code=ROLE_ADMIN,
        name="系统管理员",
        description="拥有全部管理权限",
        permissions=[SUPERUSER_PERMISSION],
        is_system=True,
    )

    await _upsert_role(
        db,
        code=ROLE_USER,
        name="普通用户",
        description="知识问答与术语查询",
        permissions=list(DEFAULT_USER_PERMISSIONS),
        is_system=True,
    )

    await db.commit()

    user_count = await db.scalar(select(func.count()).select_from(User))
    if user_count:
        return

    logger.warning(
        "users table is empty — creating bootstrap administrator %r",
        settings.bootstrap_admin_username,
    )
    admin = User(
        username=settings.bootstrap_admin_username,
        display_name=settings.bootstrap_admin_display_name,
        password_hash=hash_password(settings.bootstrap_admin_password),
        is_active=True,
        is_superuser=True,
        # Force a password change: the bootstrap password lives in configuration.
        must_change_password=True,
    )
    db.add(admin)
    await db.flush()

    admin_role = (
        await db.execute(select(Role).where(Role.code == ROLE_ADMIN))
    ).scalar_one()
    db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    await db.commit()

    logger.warning(
        "bootstrap administrator created (username=%s) — change the password on first login",
        settings.bootstrap_admin_username,
    )


async def role_by_code(db: AsyncSession, code: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.code == code))
    return result.scalar_one_or_none()
