"""app/core/permissions.py - Central RBAC permission map."""

from __future__ import annotations

from app.core.constants import UserRole


PERMISSIONS = {
    "cases:view",
    "cases:create",
    "cases:update",
    "cases:approve",
    "cases:assign",
    "cases:close",
    "cases:delete",
    "volunteers:view",
    "volunteers:create",
    "volunteers:update",
    "orgs:view",
    "orgs:create",
    "orgs:update",
    "users:create_org_admin",
    "users:create_org_manager",
    "users:create_volunteer",
    "alerts:view",
    "alerts:create",
    "alerts:resolve",
    "inventory:view",
    "inventory:manage",
    "households:view",
    "households:manage",
    "reports:view",
    "admin:forms",
    "admin:audit_logs",
    "admin:settings",
}


DEVADMIN_PERMISSIONS = set(PERMISSIONS)

ORG_ADMIN_PERMISSIONS = {
    "cases:view",
    "cases:create",
    "cases:update",
    "cases:approve",
    "cases:assign",
    "cases:close",
    "cases:delete",
    "volunteers:view",
    "volunteers:create",
    "volunteers:update",
    "orgs:view",
    "users:create_org_manager",
    "users:create_volunteer",
    "alerts:view",
    "alerts:create",
    "alerts:resolve",
    "inventory:view",
    "inventory:manage",
    "households:view",
    "households:manage",
    "reports:view",
    "admin:forms",
    "admin:audit_logs",
    "admin:settings",
}

ORG_MANAGER_PERMISSIONS = {
    "cases:view",
    "cases:create",
    "cases:update",
    "cases:approve",
    "cases:assign",
    "cases:close",
    "volunteers:view",
    "volunteers:create",
    "volunteers:update",
    "users:create_volunteer",
    "alerts:view",
    "alerts:create",
    "alerts:resolve",
    "inventory:view",
    "inventory:manage",
    "households:view",
    "households:manage",
    "reports:view",
    "admin:forms",
    "admin:audit_logs",
    "admin:settings",
}

FIELD_COORDINATOR_PERMISSIONS = {
    "cases:view",
    "cases:create",
    "cases:update",
    "cases:assign",
    "volunteers:view",
    "alerts:view",
    "alerts:create",
    "inventory:view",
    "inventory:manage",
    "households:view",
    "households:manage",
    "reports:view",
}

REVIEWER_PERMISSIONS = {
    "cases:view",
    "cases:approve",
    "cases:close",
    "alerts:view",
    "reports:view",
}

VOLUNTEER_PERMISSIONS = {
    "cases:view",
    "volunteers:view",
    "alerts:view",
    "households:view",
}


ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.super_admin: DEVADMIN_PERMISSIONS,
    UserRole.admin: ORG_ADMIN_PERMISSIONS,
    UserRole.org_manager: ORG_MANAGER_PERMISSIONS,
    UserRole.field_coordinator: FIELD_COORDINATOR_PERMISSIONS,
    UserRole.reviewer: REVIEWER_PERMISSIONS,
    UserRole.volunteer: VOLUNTEER_PERMISSIONS,
}

ROLE_LABELS: dict[UserRole, str] = {
    UserRole.super_admin: "DEVADMIN",
    UserRole.admin: "ORG_ADMIN",
    UserRole.org_manager: "ORG_MANAGER",
    UserRole.field_coordinator: "FIELD_COORDINATOR",
    UserRole.reviewer: "REVIEWER",
    UserRole.volunteer: "VOLUNTEER",
}


def has_permissions(role: UserRole, required_permissions: set[str]) -> bool:
    """Return True when a role includes all requested permissions."""
    allowed = ROLE_PERMISSIONS.get(role, set())
    return required_permissions.issubset(allowed)


def list_permissions_for_role(role: UserRole) -> set[str]:
    """Expose permissions for UI/useful API responses."""
    return set(ROLE_PERMISSIONS.get(role, set()))


def role_label(role: UserRole) -> str:
    """Human-readable role labels used by the frontend."""
    return ROLE_LABELS.get(role, role.value.upper())
