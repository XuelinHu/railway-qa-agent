"""Administration console: roles and permissions."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from app.api.deps import DbSession, client_ip, require_permission
from app.core.permissions import (
    PERM_ROLE_CREATE,
    PERM_ROLE_DELETE,
    PERM_ROLE_READ,
    PERM_ROLE_UPDATE,
    permission_tree,
)
from app.db.pagination import paginate
from app.models import Role
from app.schemas.admin import (
    PermissionNode,
    RoleCreate,
    RolePermissionsUpdate,
    RoleRead,
    RoleUpdate,
)
from app.schemas.common import MessageResponse, Page, PageParams
from app.services import audit_service
from app.services.role_service import ROLE_LOAD_OPTIONS, RoleService, to_read

router = APIRouter()

ReadRole = Annotated[object, Depends(require_permission(PERM_ROLE_READ))]
CreateRole = Annotated[object, Depends(require_permission(PERM_ROLE_CREATE))]
UpdateRole = Annotated[object, Depends(require_permission(PERM_ROLE_UPDATE))]
DeleteRole = Annotated[object, Depends(require_permission(PERM_ROLE_DELETE))]


@router.get("", response_model=Page[RoleRead])
async def list_roles(
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    _: ReadRole,
) -> Page[RoleRead]:
    service = RoleService(db)
    page = await paginate(
        db,
        select(Role).options(*ROLE_LOAD_OPTIONS),
        params,
        sortable={"created_at": Role.created_at, "code": Role.code, "name": Role.name},
        default_sort="created_at",
        search_columns=(Role.code, Role.name, Role.description),
    )
    counts = await service.user_counts()
    return Page[RoleRead].build(
        items=[to_read(role, user_count=counts.get(role.id, 0)) for role in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/permissions", response_model=list[PermissionNode])
async def list_permissions(_: ReadRole) -> list[PermissionNode]:
    """The permission registry as a tree, used by the role editor."""
    return [PermissionNode(**node) for node in permission_tree()]


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: DbSession,
    actor: CreateRole,
    request: Request,
) -> RoleRead:
    role = await RoleService(db).create(
        payload, actor_is_superuser=actor.is_superuser
    )
    await audit_service.record(
        db,
        action="role.create",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="role",
        target_id=str(role.id),
        detail={"code": role.code, "permissions": payload.permissions},
        ip_address=client_ip(request),
        commit=True,
    )
    return to_read(role)


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(role_id: uuid.UUID, db: DbSession, _: ReadRole) -> RoleRead:
    service = RoleService(db)
    role = await service.get(role_id)
    counts = await service.user_counts()
    return to_read(role, user_count=counts.get(role.id, 0))


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: DbSession,
    actor: UpdateRole,
    request: Request,
) -> RoleRead:
    service = RoleService(db)
    role = await service.get(role_id)
    role = await service.update(role, payload)
    await audit_service.record(
        db,
        action="role.update",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="role",
        target_id=str(role_id),
        detail=payload.model_dump(exclude_unset=True),
        ip_address=client_ip(request),
        commit=True,
    )
    return to_read(role)


@router.put("/{role_id}/permissions", response_model=RoleRead)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsUpdate,
    db: DbSession,
    actor: UpdateRole,
    request: Request,
) -> RoleRead:
    service = RoleService(db)
    role = await service.get(role_id)
    role = await service.set_permissions(
        role, payload.permissions, actor_is_superuser=actor.is_superuser
    )
    await audit_service.record(
        db,
        action="role.set_permissions",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="role",
        target_id=str(role_id),
        detail={"permissions": payload.permissions},
        ip_address=client_ip(request),
        commit=True,
    )
    return to_read(role)


@router.delete("/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: uuid.UUID,
    db: DbSession,
    actor: DeleteRole,
    request: Request,
) -> MessageResponse:
    service = RoleService(db)
    role = await service.get(role_id)
    code = role.code
    await service.delete(role)
    await audit_service.record(
        db,
        action="role.delete",
        user_id=actor.user.id,
        username=actor.user.username,
        target_type="role",
        target_id=str(role_id),
        detail={"code": code},
        ip_address=client_ip(request),
        commit=True,
    )
    return MessageResponse(message="角色已删除")
