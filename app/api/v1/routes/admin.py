"""app/api/v1/routes/admin.py — Admin forms, audit logs, and settings endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_roles
from app.core.constants import UserRole
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.form_template import FormTemplate
from app.models.user import User
from app.schemas.audit_log import AuditLogOut
from app.schemas.common import APIResponse, PaginatedResponse
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(prefix="/admin", tags=["Admin"])

ADMIN_ROLES = (UserRole.super_admin, UserRole.admin, UserRole.org_manager)


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
def list_audit_logs(
    entity_type: str = None,
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """View immutable audit trail. Filterable by entity type."""
    q = select(AuditLog).where(AuditLog.organization_id == current_user.organization_id)
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
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
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
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
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
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
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
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Get organization-level settings."""
    from app.models.organization import Organization
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
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
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
