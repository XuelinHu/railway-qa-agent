"""Menu and permission registry.

This module is the single source of truth for what the admin console exposes.
It drives three consumers at once:

* the backend route guards (``require_permission``),
* the frontend sidebar (``/api/auth/me`` returns the resolved menu tree),
* the role editor's permission checkbox tree.

Menus live in code rather than in a table because a menu exists precisely
because a route exists; keeping them together means they cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Permission codes. Grouped by the menu that owns them.
PERM_USER_READ = "user:read"
PERM_USER_CREATE = "user:create"
PERM_USER_UPDATE = "user:update"
PERM_USER_DELETE = "user:delete"
PERM_USER_RESET_PASSWORD = "user:reset-password"
PERM_USER_ASSIGN_ROLE = "user:assign-role"

PERM_ROLE_READ = "role:read"
PERM_ROLE_CREATE = "role:create"
PERM_ROLE_UPDATE = "role:update"
PERM_ROLE_DELETE = "role:delete"

PERM_CHAT_READ = "chat:read"
PERM_CHAT_DELETE = "chat:delete"

PERM_TERMINOLOGY_READ = "terminology:read"
PERM_TERMINOLOGY_CREATE = "terminology:create"
PERM_TERMINOLOGY_UPDATE = "terminology:update"
PERM_TERMINOLOGY_DELETE = "terminology:delete"
PERM_TERMINOLOGY_IMPORT = "terminology:import"

PERM_MODEL_READ = "model:read"
PERM_MODEL_MANAGE = "model:manage"
PERM_MODEL_PULL = "model:pull"
PERM_MODEL_SWITCH = "model:switch"

PERM_DASHBOARD_READ = "dashboard:read"

SUPERUSER_PERMISSION = "*"


@dataclass(frozen=True)
class MenuDef:
    key: str
    title: str
    path: str
    icon: str = ""
    perm: str | None = None
    children: tuple[MenuDef, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "path": self.path,
            "icon": self.icon,
            "perm": self.perm,
            "children": [child.to_dict() for child in self.children],
        }


MENUS: tuple[MenuDef, ...] = (
    MenuDef(
        key="dashboard",
        title="概览",
        path="/admin/dashboard",
        icon="DataLine",
        perm=PERM_DASHBOARD_READ,
    ),
    MenuDef(
        key="users",
        title="用户管理",
        path="/admin/users",
        icon="User",
        perm=PERM_USER_READ,
    ),
    MenuDef(
        key="roles",
        title="角色权限",
        path="/admin/roles",
        icon="Key",
        perm=PERM_ROLE_READ,
    ),
    MenuDef(
        key="conversations",
        title="对话与消息",
        path="/admin/conversations",
        icon="ChatDotRound",
        perm=PERM_CHAT_READ,
    ),
    MenuDef(
        key="terminology",
        title="术语库管理",
        path="/admin/terminology",
        icon="Collection",
        perm=PERM_TERMINOLOGY_READ,
    ),
    MenuDef(
        key="models",
        title="模型管理",
        path="/admin/models",
        icon="Cpu",
        perm=PERM_MODEL_READ,
    ),
)


def all_menu_keys() -> list[str]:
    keys: list[str] = []

    def walk(items: tuple[MenuDef, ...]) -> None:
        for item in items:
            keys.append(item.key)
            walk(item.children)

    walk(MENUS)
    return keys


def all_permissions() -> list[str]:
    """Every permission code the system knows about, plus the superuser wildcard."""
    perms: set[str] = set()

    def walk(items: tuple[MenuDef, ...]) -> None:
        for item in items:
            if item.perm:
                perms.add(item.perm)
            walk(item.children)

    walk(MENUS)
    perms.update(
        {
            PERM_USER_CREATE,
            PERM_USER_UPDATE,
            PERM_USER_DELETE,
            PERM_USER_RESET_PASSWORD,
            PERM_USER_ASSIGN_ROLE,
            PERM_ROLE_CREATE,
            PERM_ROLE_UPDATE,
            PERM_ROLE_DELETE,
            PERM_CHAT_DELETE,
            PERM_TERMINOLOGY_CREATE,
            PERM_TERMINOLOGY_UPDATE,
            PERM_TERMINOLOGY_DELETE,
            PERM_TERMINOLOGY_IMPORT,
            PERM_MODEL_MANAGE,
            PERM_MODEL_PULL,
            PERM_MODEL_SWITCH,
        }
    )
    return sorted(perms)


def menus_for(permissions: set[str] | frozenset[str]) -> list[dict]:
    """Resolve the menu tree visible to a principal.

    Menu visibility is derived entirely from permission codes: a menu guarded by
    ``user:read`` appears exactly when the principal holds it. A superuser
    (``*``) sees everything the registry defines.
    """
    is_superuser = SUPERUSER_PERMISSION in permissions

    def allowed(item: MenuDef) -> bool:
        if is_superuser or item.perm is None:
            return True
        return item.perm in permissions

    def build(items: tuple[MenuDef, ...]) -> list[dict]:
        resolved: list[dict] = []
        for item in items:
            if not allowed(item):
                continue
            payload = item.to_dict()
            payload["children"] = build(item.children)
            resolved.append(payload)
        return resolved

    return build(MENUS)


def permission_tree() -> list[dict]:
    """The full registry as a tree, for the role editor's checkbox tree."""
    def build(items: tuple[MenuDef, ...]) -> list[dict]:
        return [
            {
                "key": item.key,
                "title": item.title,
                "perm": item.perm,
                "children": build(item.children),
            }
            for item in items
        ]

    return build(MENUS)
