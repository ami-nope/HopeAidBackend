"""app/api/v1/routes/admin.py — Admin forms, audit logs, and settings endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_permissions
from app.core.constants import UserRole
from app.core.permissions import has_permissions
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.form_template import FormTemplate
from app.models.organization import Organization
from app.models.user import User
from app.models.volunteer import Volunteer
from app.schemas.admin import AdminUserCreate
from app.schemas.audit_log import AuditLogOut
from app.schemas.auth import UserOut
from app.schemas.common import APIResponse, PaginatedResponse
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
def list_audit_logs(
    entity_type: str = None,
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("admin:audit_logs")),
):
    """View immutable audit trail. Filterable by entity type."""
    q = select(AuditLog)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(AuditLog.organization_id == current_user.organization_id)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)

    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    logs = db.execute(
        q.order_by(AuditLog.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    ).scalars().all()
    return {
        "success": True,
        "data": [AuditLogOut.model_validate(log) for log in logs],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.get("/forms", response_model=APIResponse[list])
def list_forms(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("admin:forms")),
):
    forms = db.execute(
        select(FormTemplate).where(
            FormTemplate.organization_id == current_user.organization_id,
            FormTemplate.is_active == True,
        )
    ).scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": str(f.id),
                "form_name": f.form_name,
                "fields_json": f.fields_json,
                "version": f.version,
                "is_active": f.is_active,
            }
            for f in forms
        ],
    }


@router.post("/forms", response_model=APIResponse[dict], status_code=201)
def create_form(
    form_name: str,
    fields_json: list,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("admin:forms")),
):
    form = FormTemplate(
        organization_id=current_user.organization_id,
        form_name=form_name,
        fields_json=fields_json,
        created_by_user_id=current_user.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    return {"success": True, "data": {"id": str(form.id), "form_name": form.form_name}}


@router.put("/forms/{form_id}", response_model=APIResponse[dict])
def update_form(
    form_id: UUID,
    fields_json: list,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("admin:forms")),
):
    form = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == form_id,
            FormTemplate.organization_id == current_user.organization_id,
        )
    ).scalars().first()
    if not form:
        raise HTTPException(404, "Form template not found")

    form.fields_json = fields_json
    form.version += 1
    db.commit()
    return {"success": True, "data": {"id": str(form.id), "version": form.version}}


@router.get("/settings", response_model=APIResponse[dict])
def get_admin_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("admin:settings")),
):
    """Get organization-level settings."""
    from app.models.organization import Organization
    if current_user.role == UserRole.super_admin and current_user.organization_id is None:
        return {
            "success": True,
            "data": {
                "organization_id": "",
                "name": "Platform Scope",
                "slug": "platform",
                "status": "active",
                "settings": {},
            },
        }
    org = db.get(Organization, current_user.organization_id)
    return {
        "success": True,
        "data": {
            "organization_id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "status": org.status.value,
            "settings": org.settings_json or {},
        },
    }


@router.put("/settings", response_model=APIResponse[dict])
def update_admin_settings(
    new_settings: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("admin:settings")),
):
    """Update organization-level settings JSON blob."""
    from app.models.organization import Organization
    org = db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    existing = org.settings_json or {}
    existing.update(new_settings)
    org.settings_json = existing
    db.commit()
    return {"success": True, "data": {"settings": org.settings_json}}


@router.post("/users", response_model=APIResponse[UserOut], status_code=201)
def create_user_account(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an organization-scoped user account with role constraints.
    """
    role_permission_map = {
        UserRole.admin: "users:create_org_admin",
        UserRole.org_manager: "users:create_org_manager",
        UserRole.volunteer: "users:create_volunteer",
        UserRole.field_coordinator: "users:create_volunteer",
        UserRole.reviewer: "users:create_volunteer",
    }
    required_permission = role_permission_map.get(data.role)
    if not required_permission:
        raise HTTPException(400, "Unsupported role for admin user creation")
    if not has_permissions(current_user.role, {required_permission}):
        raise HTTPException(403, "Insufficient permissions for this role")

    is_super_admin = current_user.role == UserRole.super_admin
    is_global_super_admin = is_super_admin and current_user.organization_id is None

    if data.role == UserRole.admin and not is_super_admin:
        raise HTTPException(403, "Only DEVADMIN can create org admin accounts")

    target_org_id = data.organization_id or current_user.organization_id
    if target_org_id is None:
        raise HTTPException(400, "organization_id is required")

    if not is_global_super_admin and target_org_id != current_user.organization_id:
        raise HTTPException(403, "Cannot create users for another organization")

    org = db.get(Organization, target_org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    existing = db.execute(
        select(User).where(User.email == data.email.lower())
    ).scalars().first()
    if existing:
        raise HTTPException(400, "Email already registered")

    display_name = data.name
    if data.role == UserRole.admin and not display_name:
        display_name = f"{org.slug.upper()}-ADMIN"
    if not display_name:
        raise HTTPException(400, "name is required")

    user = User(
        organization_id=target_org_id,
        name=display_name,
        email=data.email.lower(),
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    if data.create_volunteer_profile or data.role == UserRole.volunteer:
        volunteer = Volunteer(
            organization_id=target_org_id,
            user_id=user.id,
            name=user.name,
            phone=user.phone,
            email=user.email,
        )
        db.add(volunteer)

    db.commit()
    db.refresh(user)
    return {"success": True, "data": UserOut.model_validate(user)}
