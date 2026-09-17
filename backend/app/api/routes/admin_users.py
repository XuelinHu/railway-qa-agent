"""Administration console: user management."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, client_ip, require_permission
from app.core.permissions import (
    PERM_USER_ASSIGN_ROLE,
    PERM_USER_CREATE,
    PERM_USER_DELETE,
    PERM_USER_READ,
    PERM_USER_RESET_PASSWORD,
    PERM_USER_UPDATE,
)
from app.db.pagination import paginate
from app.models import Role, User, UserRole
from app.schemas.admin import (
    AdminResetPasswordRequest,
    AssignRolesRequest,
    IssueResetTokenResponse,
    ResetRequestRead,
    UserAdminCreate,
    UserAdminRead,
    UserAdminUpdate,
)
from app.schemas.common import MessageResponse, Page, PageParams
from app.services import audit_service
from app.services.user_service import ResetRequestService, UserService, to_read

router = APIRouter()

ReadUser = Annotated[object, Depends(require_permission(PERM_USER_READ))]
CreateUser = Annotated[object, Depends(require_permission(PERM_USER_CREATE))]
UpdateUser = Annotated[object, Depends(require_permission(PERM_USER_UPDATE))]
DeleteUser = Annotated[object, Depends(require_permission(PERM_USER_DELETE))]
ResetUser = Annotated[object, Depends(require_permission(PERM_USER_RESET_PASSWORD))]
AssignRole = Annotated[object, Depends(require_permission(PERM_USER_ASSIGN_ROLE))]


@router.get("", response_model=Page[UserAdminRead])
async def list_users(
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    _: ReadUser,
    is_active: Annotated[bool | None, Query()] = None,
    role_code: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[UserAdminRead]:
    stmt = select(User).options(selectinload(User.role_links).selectinload(UserRole.role))

    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if role_code:
        stmt = stmt.join(UserRole, UserRole.user_id == User.id).join(
            Role, Role.id == UserRole.role_id
        ).where(Role.code == role_code)

    page = await paginate(
        db,
        stmt,
        params,
        sortable={"created_at": User.created_at, "username": User.username},
        default_sort="created_at",
        search_columns=(User.username, User.display_name, User.email),
    )
    return Page[UserAdminRead].build(
        items=[to_read(user) for user in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/reset-requests", response_model=list[ResetRequestRead])
async def list_reset_requests(db: DbSession, _: ReadUser) -> list[ResetRequestRead]:
    rows = await ResetRequestService(db).list_pending()
    return [ResetRequestRead(**row) for row in rows]


@router.post(
    "/reset-requests/{request_id}/issue",
    response_model=IssueResetTokenResponse,
)
async def issue_reset_token(
    request_id: uuid.UUID,
    db: DbSession,
    actor: Annotated[object, Depends(require_permission(PERM_USER_RESET_PASSWORD))],
    request: Request,
) -> IssueResetTokenResponse:
    token, expires_at = await ResetRequestService(db).issue_token(
        request_id, actor_id=actor.user.id
    )
    await audit_service.record(
        db,
        action="user.issue_reset_token",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="password_reset_request",
        target_id=str(request_id),
        ip_address=client_ip(request),
        commit=True,
    )
    return IssueResetTokenResponse(
        token=token,
        expires_at=expires_at,
        message="请将重置令牌转交申请人，1 小时内有效。",
    )


@router.post("", response_model=UserAdminRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserAdminCreate,
    db: DbSession,
    actor: CreateUser,
    request: Request,
) -> UserAdminRead:
    user = await UserService(db).create(payload)
    await audit_service.record(
        db,
        action="user.create",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="user",
        target_id=str(user.id),
        detail={"username": user.username},
        ip_address=client_ip(request),
        commit=True,
    )
    return to_read(user)


@router.get("/{user_id}", response_model=UserAdminRead)
async def get_user(user_id: uuid.UUID, db: DbSession, _: ReadUser) -> UserAdminRead:
    return to_read(await UserService(db).get(user_id))


@router.patch("/{user_id}", response_model=UserAdminRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    db: DbSession,
    actor: UpdateUser,
    request: Request,
) -> UserAdminRead:
    service = UserService(db)
    user = await service.get(user_id)
    changes = payload.model_dump(exclude_unset=True)
    user = await service.update(user, changes)
    await audit_service.record(
        db,
        action="user.update",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="user",
        target_id=str(user_id),
        detail=changes,
        ip_address=client_ip(request),
        commit=True,
    )
    return to_read(user)


@router.put("/{user_id}/roles", response_model=UserAdminRead)
async def assign_roles(
    user_id: uuid.UUID,
    payload: AssignRolesRequest,
    db: DbSession,
    actor: AssignRole,
    request: Request,
) -> UserAdminRead:
    service = UserService(db)
    user = await service.get(user_id)
    user = await service.assign_roles(user, payload.role_codes)
    await audit_service.record(
        db,
        action="user.assign_roles",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="user",
        target_id=str(user_id),
        detail={"roles": payload.role_codes},
        ip_address=client_ip(request),
        commit=True,
    )
    return to_read(user)


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_password(
    user_id: uuid.UUID,
    payload: AdminResetPasswordRequest,
    db: DbSession,
    actor: ResetUser,
    request: Request,
) -> MessageResponse:
    service = UserService(db)
    user = await service.get(user_id)
    await service.set_password(
        user, payload.new_password, require_change=payload.require_change
    )
    await audit_service.record(
        db,
        action="user.reset_password",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="user",
        target_id=str(user_id),
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message="密码已重置，该用户的登录状态已全部失效")


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: uuid.UUID,
    db: DbSession,
    actor: DeleteUser,
    request: Request,
) -> MessageResponse:
    service = UserService(db)
    user = await service.get(user_id)
    username = user.username
    await service.delete(user, actor_id=actor.user.id)
    await audit_service.record(
        db,
        action="user.delete",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="user",
        target_id=str(user_id),
        detail={"username": username},
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message="用户已删除")
