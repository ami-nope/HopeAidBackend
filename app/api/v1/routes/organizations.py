"""app/api/v1/routes/organizations.py — Organization management endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_roles
from app.core.constants import UserRole
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.organization import OrgCreate, OrgOut, OrgUpdate

router = APIRouter(prefix="/orgs", tags=["Organizations"])


@router.post("", response_model=APIResponse[OrgOut], status_code=201)
def create_org(
    data: OrgCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.super_admin)),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
