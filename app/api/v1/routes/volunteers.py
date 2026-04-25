"""app/api/v1/routes/volunteers.py — Volunteer management endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.volunteer import Volunteer, VolunteerAvailability
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.volunteer import (
    AvailabilitySlotCreate,
    AvailabilitySlotOut,
    VolunteerCreate,
    VolunteerOut,
    VolunteerUpdate,
)
from app.services.audit_service import log_action
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(prefix="/volunteers", tags=["Volunteers"])


@router.post("", response_model=APIResponse[VolunteerOut], status_code=201)
def create_volunteer(
    data: VolunteerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vol = Volunteer(
        organization_id=current_user.organization_id,
        **data.model_dump(),
    )
    db.add(vol)
    db.flush()
    log_action(
        db, current_user.organization_id, current_user.id,
        "VOLUNTEER_CREATED", "volunteer", vol.id,
        after_json={"name": vol.name},
    )
    db.commit()
    db.refresh(vol)
    return {"success": True, "data": VolunteerOut.model_validate(vol)}


@router.get("", response_model=PaginatedResponse[VolunteerOut])
def list_volunteers(
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Volunteer).where(Volunteer.organization_id == current_user.organization_id)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    volunteers = db.execute(q.offset(pagination.offset).limit(pagination.page_size)).scalars().all()
    return {
        "success": True,
        "data": [VolunteerOut.model_validate(v) for v in volunteers],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.get("/{volunteer_id}", response_model=APIResponse[VolunteerOut])
def get_volunteer(
    volunteer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vol = db.execute(
        select(Volunteer).where(
            Volunteer.id == volunteer_id,
            Volunteer.organization_id == current_user.organization_id,
        )
    ).scalars().first()
    if not vol:
        raise HTTPException(404, "Volunteer not found")
    return {"success": True, "data": VolunteerOut.model_validate(vol)}


@router.put("/{volunteer_id}", response_model=APIResponse[VolunteerOut])
def update_volunteer(
    volunteer_id: UUID,
    data: VolunteerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vol = db.execute(
        select(Volunteer).where(
            Volunteer.id == volunteer_id,
            Volunteer.organization_id == current_user.organization_id,
        )
    ).scalars().first()
    if not vol:
        raise HTTPException(404, "Volunteer not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(vol, field, value)

    db.commit()
    db.refresh(vol)
    return {"success": True, "data": VolunteerOut.model_validate(vol)}


@router.post("/{volunteer_id}/availability", response_model=APIResponse[AvailabilitySlotOut], status_code=201)
def add_availability(
    volunteer_id: UUID,
    data: AvailabilitySlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify volunteer belongs to this org
    vol = db.execute(
        select(Volunteer).where(
            Volunteer.id == volunteer_id,
            Volunteer.organization_id == current_user.organization_id,
        )
    ).scalars().first()
    if not vol:
        raise HTTPException(404, "Volunteer not found")

    slot = VolunteerAvailability(volunteer_id=volunteer_id, **data.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"success": True, "data": AvailabilitySlotOut.model_validate(slot)}


@router.get("/{volunteer_id}/availability", response_model=APIResponse[list[AvailabilitySlotOut]])
def get_availability(
    volunteer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slots = db.execute(
        select(VolunteerAvailability).where(
            VolunteerAvailability.volunteer_id == volunteer_id
        )
    ).scalars().all()
    return {
        "success": True,
        "data": [AvailabilitySlotOut.model_validate(s) for s in slots],
    }
