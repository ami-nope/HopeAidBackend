"""app/api/v1/routes/organizations.py — Organization management endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_permissions
from app.core.constants import UserRole
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.organization import OrgCreate, OrgOut, OrgUpdate
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(prefix="/orgs", tags=["Organizations"])


@router.get("", response_model=PaginatedResponse[OrgOut])
def list_orgs(
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("orgs:view")),
):
    from app.models.organization import Organization

    q = select(Organization)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Organization.id == current_user.organization_id)

    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    orgs = db.execute(
        q.order_by(Organization.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    ).scalars().all()
    return {
        "success": True,
        "data": [OrgOut.model_validate(org) for org in orgs],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.post("", response_model=APIResponse[OrgOut], status_code=201)
def create_org(
    data: OrgCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("orgs:create")),
):
    """Create a new organization (super_admin only)."""
    from app.models.organization import Organization

    existing = db.execute(
        select(Organization).where(Organization.slug == data.slug)
    ).scalars().first()
    if existing:
        raise HTTPException(400, "Organization slug already taken")

    org = Organization(**data.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return {"success": True, "data": OrgOut.model_validate(org)}


@router.get("/{org_id}", response_model=APIResponse[OrgOut])
def get_org(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("orgs:view")),
):
    """Get organization details. Users can only view their own org."""
    from app.models.organization import Organization

    if current_user.role != UserRole.super_admin and current_user.organization_id != org_id:
        raise HTTPException(403, "Access denied to this organization")

    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    return {"success": True, "data": OrgOut.model_validate(org)}


@router.put("/{org_id}", response_model=APIResponse[OrgOut])
def update_org(
    org_id: UUID,
    data: OrgUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("orgs:update")),
):
    """Update organization settings. Requires admin or org_manager role."""
    from app.core.constants import ORG_MANAGERS
    from app.models.organization import Organization

    if current_user.role not in ORG_MANAGERS:
        raise HTTPException(403, "Insufficient permissions")
    if current_user.role != UserRole.super_admin and current_user.organization_id != org_id:
        raise HTTPException(403, "Access denied to this organization")

    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(org, field, value)

    db.commit()
    db.refresh(org)
    return {"success": True, "data": OrgOut.model_validate(org)}
