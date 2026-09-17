"""Registration, login, session refresh and password lifecycle."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.permissions import SUPERUSER_PERMISSION, menus_for
from app.core.ratelimit import LoginThrottle
from app.core.security import (
    access_token_expires_in,
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.seed import ROLE_USER, role_by_code
from app.models import PasswordResetRequest, RefreshToken, Role, User, UserRole
from app.schemas.auth import RegisterRequest

logger = logging.getLogger(__name__)

login_throttle = LoginThrottle(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_lockout_seconds,
)

GENERIC_LOGIN_ERROR = "用户名或密码错误"


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- registration -------------------------------------------------------
    async def register(
        self,
        payload: RegisterRequest,
        *,
        is_active: bool = True,
        grant_default_role: bool = True,
    ) -> User:
        existing = await self.db.scalar(
            select(User).where(User.username == payload.username)
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="该用户名已被注册")

        if payload.email:
            email_taken = await self.db.scalar(
                select(User).where(User.email == payload.email)
            )
            if email_taken is not None:
                raise HTTPException(status_code=409, detail="该邮箱已被注册")

        user = User(
            username=payload.username,
            display_name=payload.display_name or payload.username,
            email=payload.email,
            password_hash=await run_in_threadpool(hash_password, payload.password),
            is_active=is_active,
        )
        self.db.add(user)
        await self.db.flush()

        if grant_default_role:
            role = await role_by_code(self.db, ROLE_USER)
            if role is not None:
                self.db.add(UserRole(user_id=user.id, role_id=role.id))

        await self.db.commit()
        return await self.load_user(user.id)

    # --- login --------------------------------------------------------------
    async def authenticate(
        self,
        username: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Return ``(user, access_token, refresh_token)`` or raise 401."""
        retry_after = login_throttle.retry_after(username, ip)
        if retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录失败次数过多，请 {retry_after} 秒后重试",
                headers={"Retry-After": str(retry_after)},
            )

        user = await self.db.scalar(select(User).where(User.username == username))
        # Always run a verification so a missing account and a wrong password
        # take the same amount of time.
        reference = user.password_hash if user is not None else None
        password_ok = await run_in_threadpool(verify_password, password, reference)

        if user is None or not password_ok:
            login_throttle.record_failure(username, ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_LOGIN_ERROR,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(status_code=403, detail="该账号已被禁用，请联系管理员")

        login_throttle.reset(username, ip)
        user.last_login_at = datetime.now(UTC)
        user.login_count = (user.login_count or 0) + 1
        await self.db.commit()

        user = await self.load_user(user.id)
        access_token, _ = create_access_token(user.id, user.username, list(user.role_codes))
        refresh_token, refresh_expires = self._issue_refresh_token(
            user.id, user_agent=user_agent, ip=ip
        )
        await self.db.commit()
        return user, access_token, refresh_token

    def _issue_refresh_token(
        self,
        user_id: uuid.UUID,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> tuple[str, datetime]:
        raw = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
        self.db.add(
            RefreshToken(
                user_id=user_id,
                token_hash=hash_token(raw),
                expires_at=expires_at,
                user_agent=(user_agent or "")[:400] or None,
                ip_address=(ip or "")[:64] or None,
            )
        )
        return raw, expires_at

    # --- refresh / logout ---------------------------------------------------
    async def refresh(
        self,
        raw_token: str,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> tuple[User, str, str]:
        now = datetime.now(UTC)
        record = await self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        )
        if record is None or record.revoked_at is not None or record.expires_at <= now:
            raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")

        user = await self.load_user(record.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="账号不可用，请重新登录")

        # Rotate: the presented token is burned and a fresh one issued.
        record.revoked_at = now
        new_raw, _ = self._issue_refresh_token(user.id, user_agent=user_agent, ip=ip)
        await self.db.commit()

        access_token, _ = create_access_token(user.id, user.username, list(user.role_codes))
        return user, access_token, new_raw

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == hash_token(raw_token),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.commit()

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    # --- password -----------------------------------------------------------
    async def change_password(
        self, user: User, old_password: str, new_password: str
    ) -> None:
        ok = await run_in_threadpool(verify_password, old_password, user.password_hash)
        if not ok:
            raise HTTPException(status_code=400, detail="原密码不正确")
        if old_password == new_password:
            raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

        user.password_hash = await run_in_threadpool(hash_password, new_password)
        user.must_change_password = False
        # A password change invalidates every existing session.
        await self.revoke_all_sessions(user.id)
        await self.db.commit()

    async def request_password_reset(self, username: str) -> tuple[User | None, str | None]:
        """Create a reset request. Returns ``(user, raw_token)``.

        Unknown usernames return ``(None, None)`` so the endpoint cannot be used
        to enumerate accounts.
        """
        user = await self.db.scalar(select(User).where(User.username == username))
        if user is None or not user.is_active:
            return None, None

        raw_token = generate_opaque_token()
        self.db.add(
            PasswordResetRequest(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                status="pending",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await self.db.commit()
        return user, raw_token

    async def reset_password(self, raw_token: str, new_password: str) -> User:
        now = datetime.now(UTC)
        record = await self.db.scalar(
            select(PasswordResetRequest).where(
                PasswordResetRequest.token_hash == hash_token(raw_token)
            )
        )
        if (
            record is None
            or record.used_at is not None
            or record.expires_at is None
            or record.expires_at <= now
        ):
            raise HTTPException(status_code=400, detail="重置链接无效或已过期")

        user = await self.db.get(User, record.user_id)
        if user is None:
            raise HTTPException(status_code=400, detail="重置链接无效或已过期")

        user.password_hash = await run_in_threadpool(hash_password, new_password)
        user.must_change_password = False
        record.used_at = now
        record.status = "used"
        await self.revoke_all_sessions(user.id)
        await self.db.commit()
        return user

    # --- helpers ------------------------------------------------------------
    async def load_user(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.role_links)
                .selectinload(UserRole.role)
                .selectinload(Role.permission_links)
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return user


def principal_payload(user: User) -> dict:
    """The `user` / `roles` / `permissions` / `menus` block shared by auth responses."""
    roles = user.role_codes
    permissions: set[str] = set()
    for link in user.role_links:
        if link.role is None:
            continue
        permissions.update(item.permission for item in link.role.permission_links)
    if user.is_superuser:
        permissions.add(SUPERUSER_PERMISSION)

    ordered = sorted(permissions)
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "must_change_password": user.must_change_password,
            "last_login_at": user.last_login_at,
            "login_count": user.login_count,
            "created_at": user.created_at,
            "roles": roles,
        },
        "roles": roles,
        "permissions": ordered,
        "menus": menus_for(permissions),
        "expires_in": access_token_expires_in(),
    }
