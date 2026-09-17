"""Administrative user management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.core.security import generate_opaque_token, hash_password, hash_token
from app.models import PasswordResetRequest, RefreshToken, Role, User, UserRole
from app.schemas.admin import UserAdminCreate, UserAdminRead

USER_LOAD_OPTIONS = (
    selectinload(User.role_links).selectinload(UserRole.role),
)


def to_read(user: User) -> UserAdminRead:
    return UserAdminRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        login_count=user.login_count,
        created_at=user.created_at,
        roles=user.role_codes,
    )


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: UserAdminCreate) -> User:
        taken = await self.db.scalar(select(User).where(User.username == payload.username))
        if taken is not None:
            raise HTTPException(status_code=409, detail="该用户名已存在")
        if payload.email:
            email_taken = await self.db.scalar(
                select(User).where(User.email == payload.email)
            )
            if email_taken is not None:
                raise HTTPException(status_code=409, detail="该邮箱已被使用")

        user = User(
            username=payload.username,
            display_name=payload.display_name or payload.username,
            email=payload.email,
            password_hash=await run_in_threadpool(hash_password, payload.password),
            is_active=payload.is_active,
        )
        self.db.add(user)
        await self.db.flush()

        if payload.role_codes:
            await self._assign_roles(user, payload.role_codes)

        await self.db.commit()
        return await self.get(user.id)

    async def get(self, user_id: uuid.UUID) -> User:
        # populate_existing is required because the session is built with
        # expire_on_commit=False: without it a User already in the identity map
        # is returned with the role collection cached from before the write, and
        # the response to a role change would describe the previous state.
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(*USER_LOAD_OPTIONS)
            .execution_options(populate_existing=True)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return user

    async def update(self, user: User, changes: dict) -> User:
        if "email" in changes and changes["email"]:
            clash = await self.db.scalar(
                select(User).where(User.email == changes["email"], User.id != user.id)
            )
            if clash is not None:
                raise HTTPException(status_code=409, detail="该邮箱已被使用")

        for field, value in changes.items():
            if value is not None:
                setattr(user, field, value)

        await self.db.commit()
        return await self.get(user.id)

    async def assign_roles(self, user: User, role_codes: list[str]) -> User:
        await self._assign_roles(user, role_codes)
        await self.db.commit()
        return await self.get(user.id)

    async def _assign_roles(self, user: User, role_codes: list[str]) -> None:
        roles: list[Role] = []
        if role_codes:
            result = await self.db.execute(select(Role).where(Role.code.in_(role_codes)))
            roles = list(result.scalars().all())
            missing = set(role_codes) - {role.code for role in roles}
            if missing:
                raise HTTPException(
                    status_code=400, detail=f"角色不存在: {', '.join(sorted(missing))}"
                )

        await self.db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        for role in roles:
            self.db.add(UserRole(user_id=user.id, role_id=role.id))
        await self.db.flush()

    async def set_password(
        self, user: User, new_password: str, *, require_change: bool
    ) -> None:
        user.password_hash = await run_in_threadpool(hash_password, new_password)
        user.must_change_password = require_change
        # An administrative reset must invalidate whatever session was active.
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.commit()

    async def delete(self, user: User, *, actor_id: uuid.UUID) -> None:
        if user.id == actor_id:
            raise HTTPException(status_code=400, detail="不能删除当前登录的账号")
        if user.is_superuser:
            remaining = await self.db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_superuser.is_(True), User.id != user.id)
            )
            if not remaining:
                raise HTTPException(status_code=400, detail="必须保留至少一个超级管理员")
        await self.db.delete(user)
        await self.db.commit()


class ResetRequestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_pending(self, *, limit: int = 100) -> list[dict]:
        result = await self.db.execute(
            select(PasswordResetRequest, User)
            .join(User, User.id == PasswordResetRequest.user_id)
            .where(PasswordResetRequest.status == "pending")
            .order_by(PasswordResetRequest.created_at.desc())
            .limit(limit)
        )
        rows = []
        for request_row, user in result.all():
            rows.append(
                {
                    "id": request_row.id,
                    "user_id": request_row.user_id,
                    "username": user.username,
                    "display_name": user.display_name,
                    "status": request_row.status,
                    "note": request_row.note,
                    "created_at": request_row.created_at,
                    "expires_at": request_row.expires_at,
                    "used_at": request_row.used_at,
                }
            )
        return rows

    async def issue_token(
        self, request_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> tuple[str, datetime]:
        record = await self.db.get(PasswordResetRequest, request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="重置申请不存在")
        if record.status != "pending":
            raise HTTPException(status_code=400, detail="该申请已被处理")

        raw_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        record.token_hash = hash_token(raw_token)
        record.expires_at = expires_at
        record.handled_by = actor_id
        record.status = "issued"
        await self.db.commit()
        return raw_token, expires_at
