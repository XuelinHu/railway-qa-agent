from app.core.permissions import (
    MENUS,
    PERM_CHAT_READ,
    PERM_ROLE_READ,
    PERM_TERMINOLOGY_READ,
    PERM_USER_READ,
    SUPERUSER_PERMISSION,
    all_menu_keys,
    all_permissions,
    menus_for,
    permission_tree,
)


def test_menu_keys_are_unique():
    keys = all_menu_keys()
    assert len(keys) == len(set(keys))


def test_every_menu_exposes_a_permission():
    for menu in MENUS:
        assert menu.perm, f"{menu.key} has no permission code"
        assert menu.path.startswith("/")


def test_all_permissions_includes_menu_guards_and_action_codes():
    perms = set(all_permissions())
    assert {PERM_USER_READ, PERM_ROLE_READ, PERM_CHAT_READ, PERM_TERMINOLOGY_READ} <= perms
    assert "user:delete" in perms
    assert "terminology:import" in perms
    assert "model:pull" in perms
    # The superuser wildcard is a role grant, not a checkbox in the editor.
    assert SUPERUSER_PERMISSION not in perms


def test_no_menu_for_a_principal_without_permissions():
    assert menus_for(frozenset()) == []


def test_menu_visibility_follows_the_permission_code():
    menus = menus_for(frozenset({PERM_TERMINOLOGY_READ}))
    assert [menu["key"] for menu in menus] == ["terminology"]


def test_superuser_sees_every_menu():
    menus = menus_for(frozenset({SUPERUSER_PERMISSION}))
    assert [menu["key"] for menu in menus] == all_menu_keys()


def test_permission_tree_covers_the_registry():
    tree = permission_tree()
    assert [node["key"] for node in tree] == all_menu_keys()
    for node in tree:
        assert set(node) == {"key", "title", "perm", "children"}
