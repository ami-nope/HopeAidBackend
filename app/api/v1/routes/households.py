"""app/api/v1/routes/households.py — Household and Person endpoints. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import UserRole
from app.api.v1.deps import require_permissions
from app.db.session import get_db
from app.models.household import Household
from app.models.person import Person
from app.models.user import User
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.household import HouseholdCreate, HouseholdOut, HouseholdUpdate
from app.schemas.person import PersonCreate, PersonOut, PersonUpdate
from app.services.audit_service import log_action
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(tags=["Households & People"])


# ─── Households ───────────────────────────────────────────────────────────────

@router.post("/households", response_model=APIResponse[HouseholdOut], status_code=201)
def create_household(
    data: HouseholdCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("households:manage")),
):
    org_id = current_user.organization_id
    if org_id is None:
        raise HTTPException(400, "organization_id is required")

    hh = Household(
        organization_id=org_id,
        created_by_user_id=current_user.id,
        **data.model_dump(),
    )
    db.add(hh)
    db.flush()
    log_action(
        db, org_id, current_user.id,
        "HOUSEHOLD_CREATED", "household", hh.id,
        after_json={"name": hh.household_name},
    )
    db.commit()
    db.refresh(hh)
    out = HouseholdOut.model_validate(hh)
    out.person_count = 0
    return {"success": True, "data": out}


@router.get("/households", response_model=PaginatedResponse[HouseholdOut])
def list_households(
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("households:view")),
):
    q = select(Household)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Household.organization_id == current_user.organization_id)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    households = db.execute(q.offset(pagination.offset).limit(pagination.page_size)).scalars().all()
    return {
        "success": True,
        "data": [HouseholdOut.model_validate(h) for h in households],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.get("/households/{household_id}", response_model=APIResponse[HouseholdOut])
def get_household(
    household_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("households:view")),
):
    q = select(Household).where(Household.id == household_id)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Household.organization_id == current_user.organization_id)
    hh = db.execute(q).scalars().first()
    if not hh:
        raise HTTPException(404, "Household not found")

    cnt = db.execute(
        select(func.count(Person.id)).where(Person.household_id == household_id)
    ).scalar()

    out = HouseholdOut.model_validate(hh)
    out.person_count = cnt
    return {"success": True, "data": out}


@router.put("/households/{household_id}", response_model=APIResponse[HouseholdOut])
def update_household(
    household_id: UUID,
    data: HouseholdUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("households:manage")),
):
    q = select(Household).where(Household.id == household_id)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Household.organization_id == current_user.organization_id)
    hh = db.execute(q).scalars().first()
    if not hh:
        raise HTTPException(404, "Household not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(hh, field, value)

    db.commit()
    db.refresh(hh)
    return {"success": True, "data": HouseholdOut.model_validate(hh)}


# ─── Persons ──────────────────────────────────────────────────────────────────

@router.post("/people", response_model=APIResponse[PersonOut], status_code=201)
def create_person(
    data: PersonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("households:manage")),
):
    # Ensure household belongs to this org
    hh = db.get(Household, data.household_id)
    if not hh:
        raise HTTPException(404, "Household not found in your organization")
    if (
        not (current_user.role == UserRole.super_admin and current_user.organization_id is None)
        and hh.organization_id != current_user.organization_id
    ):
        raise HTTPException(404, "Household not found in your organization")

    person = Person(
        organization_id=hh.organization_id,
        **data.model_dump(),
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return {"success": True, "data": PersonOut.model_validate(person)}


@router.put("/people/{person_id}", response_model=APIResponse[PersonOut])
def update_person(
    person_id: UUID,
    data: PersonUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("households:manage")),
):
    q = select(Person).where(Person.id == person_id)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Person.organization_id == current_user.organization_id)
    person = db.execute(q).scalars().first()
    if not person:
        raise HTTPException(404, "Person not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(person, field, value)

    db.commit()
    db.refresh(person)
    return {"success": True, "data": PersonOut.model_validate(person)}
