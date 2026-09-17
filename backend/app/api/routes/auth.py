"""Public authentication endpoints: register, login, session and password."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentPrincipal, DbSession, client_ip
from app.core.config import settings
from app.core.security import access_token_expires_in
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserRead,
)
from app.schemas.common import MessageResponse
from app.services import audit_service
from app.services.auth_service import AuthService, principal_payload

logger = logging.getLogger(__name__)

router = APIRouter()

REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    max_age = settings.jwt_refresh_ttl_days * 24 * 3600
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        # SameSite=Lax plus a scoped path is the CSRF story: the cookie only ever
        # reaches the refresh endpoint, which cannot change state on its own.
        samesite="lax",
        secure=False,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession, request: Request) -> UserRead:
    user = await AuthService(db).register(payload)
    await audit_service.record(
        db,
        action="user.register",
        user_id=user.id,
        username=user.username,
        target_type="user",
        target_id=str(user.id),
        ip_address=client_ip(request),
        commit=True,
    )
    return UserRead.model_validate(
        {
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
            "roles": user.role_codes,
        }
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: DbSession,
    request: Request,
    response: Response,
) -> TokenResponse:
    service = AuthService(db)
    user, access_token, refresh_token = await service.authenticate(
        payload.username,
        payload.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, refresh_token)

    await audit_service.record(
        db,
        action="user.login",
        user_id=user.id,
        username=user.username,
        ip_address=client_ip(request),
        commit=True,
    )

    data = principal_payload(user)
    return TokenResponse(
        access_token=access_token,
        expires_in=access_token_expires_in(),
        user=data["user"],
        roles=data["roles"],
        permissions=data["permissions"],
        menus=data["menus"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(db: DbSession, request: Request, response: Response) -> TokenResponse:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")

    service = AuthService(db)
    user, access_token, new_refresh = await service.refresh(
        raw_token,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, new_refresh)

    data = principal_payload(user)
    return TokenResponse(
        access_token=access_token,
        expires_in=access_token_expires_in(),
        user=data["user"],
        roles=data["roles"],
        permissions=data["permissions"],
        menus=data["menus"],
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(db: DbSession, request: Request, response: Response) -> MessageResponse:
    await AuthService(db).logout(request.cookies.get(settings.refresh_cookie_name))
    _clear_refresh_cookie(response)
    return MessageResponse(message="已退出登录")


@router.get("/me", response_model=MeResponse)
async def me(principal: CurrentPrincipal) -> MeResponse:
    data = principal_payload(principal.user)
    return MeResponse(
        user=data["user"],
        roles=data["roles"],
        permissions=data["permissions"],
        menus=data["menus"],
    )


@router.patch("/profile", response_model=UserRead)
async def update_profile(
    payload: ProfileUpdateRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> UserRead:
    user = principal.user
    if payload.display_name is not None:
        user.display_name = payload.display_name or None
    if payload.email is not None:
        user.email = payload.email
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(
        {
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
            "roles": user.role_codes,
        }
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    request: Request,
    response: Response,
) -> MessageResponse:
    await AuthService(db).change_password(
        principal.user, payload.old_password, payload.new_password
    )
    _clear_refresh_cookie(response)
    await audit_service.record(
        db,
        action="user.change_password",
        user_id=principal.user.id,
        username=principal.user.username,
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message="密码修改成功，请重新登录")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: DbSession,
    request: Request,
) -> ForgotPasswordResponse:
    user, raw_token = await AuthService(db).request_password_reset(payload.username)

    if user is not None and settings.smtp_host and raw_token:
        await _send_reset_mail(user, raw_token)

    # The response never reveals whether the account exists.
    message = "如果该账号存在，重置申请已提交，请联系管理员获取重置链接。"
    dev_token = None
    if raw_token and settings.app_env == "development":
        # Development convenience only: there is no mail server on this box, so
        # surface the token instead of leaving the flow unusable.
        dev_token = raw_token
        message = "开发模式下已直接返回重置令牌。"
        logger.warning("password reset token issued for %s: %s", user.username, raw_token)

    if user is not None:
        await audit_service.record(
            db,
            action="user.forgot_password",
            user_id=user.id,
            username=user.username,
            ip_address=client_ip(request),
            commit=True,
        )

    return ForgotPasswordResponse(message=message, dev_reset_token=dev_token)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    await AuthService(db).reset_password(payload.token, payload.new_password)
    return MessageResponse(message="密码重置成功，请使用新密码登录")


async def _send_reset_mail(user, raw_token: str) -> None:
    """Send the reset link when SMTP is configured; log and continue otherwise."""
    link = f"{settings.public_base_url.rstrip('/')}/reset-password?token={raw_token}"
    try:
        from email.message import EmailMessage

        import aiosmtplib

        message = EmailMessage()
        message["From"] = settings.smtp_from or settings.smtp_username
        message["To"] = user.email
        message["Subject"] = "铁路知识问答系统 - 密码重置"
        greeting = user.display_name or user.username
        message.set_content(
            f"您好 {greeting}：\n\n"
            f"请打开以下链接重置密码（1 小时内有效）：\n{link}\n"
        )
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls,
        )
    except Exception:  # noqa: BLE001 - mail failure must not break the request
        logger.exception("failed to send password reset mail to %s", user.email)
