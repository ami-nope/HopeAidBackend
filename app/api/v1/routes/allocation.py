"""app/api/v1/routes/allocation.py — Volunteer allocation recommendation and confirmation. All sync."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_permissions
from app.core.constants import AssignmentStatus, UserRole
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.report import AllocationRecommendResponse
from app.services.allocation_service import AllocationService, compute_allocation_score

router = APIRouter(prefix="/allocation", tags=["Allocation"])


@router.post("/recommend", response_model=APIResponse[AllocationRecommendResponse])
def recommend_volunteers(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:view")),
):
    """
    Score and rank available volunteers for a given case.
    Returns top 5 recommendations with score breakdown and AI explanation.
    """
    try:
        service = AllocationService(db, current_user)
        result = service.recommend(case_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/confirm", response_model=APIResponse[None])
def confirm_allocation(
    case_id: UUID,
    volunteer_id: UUID,
    notes: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:assign")),
):
    """
    Confirm a volunteer recommendation — creates a real Assignment record.
    """
    from app.models.assignment import Assignment
    from app.models.case import Case
    from app.core.constants import CaseStatus
    from app.models.volunteer import Volunteer

    is_global_super_admin = (
        current_user.role == UserRole.super_admin and current_user.organization_id is None
    )

    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if not is_global_super_admin and case.organization_id != current_user.organization_id:
        raise HTTPException(404, "Case not found")

    vol_query = select(Volunteer).where(Volunteer.id == volunteer_id)
    if not is_global_super_admin:
        vol_query = vol_query.where(Volunteer.organization_id == current_user.organization_id)
    else:
        vol_query = vol_query.where(Volunteer.organization_id == case.organization_id)
    vol = db.execute(vol_query).scalars().first()
    if not vol:
        raise HTTPException(404, "Volunteer not found")

    # Compute allocation score for audit trail
    breakdown = compute_allocation_score(vol, case)

    assignment = Assignment(
        case_id=case_id,
        volunteer_id=volunteer_id,
        assigned_by_user_id=current_user.id,
        organization_id=case.organization_id,
        status=AssignmentStatus.pending,
        allocation_score=breakdown["total"],
        reasoning=breakdown,
        notes=notes,
    )
    db.add(assignment)
    vol.active_assignment_count += 1
    case.status = CaseStatus.assigned
    db.commit()
    return {"success": True, "message": "Volunteer allocation confirmed"}


@router.post("/conflict-check", response_model=APIResponse[dict])
def conflict_check(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:view")),
):
    """Check for inventory shortages and other operational conflicts for a case."""
    try:
        service = AllocationService(db, current_user)
        result = service.conflict_check(case_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/resource-optimization", response_model=APIResponse[dict])
def resource_optimization(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    """Overview of resource allocation efficiency: unassigned urgent cases vs idle volunteers."""
    from app.models.case import Case
    from app.models.volunteer import Volunteer
    from app.core.constants import CaseStatus, UrgencyLevel, AvailabilityStatus

    is_global_super_admin = (
        current_user.role == UserRole.super_admin and current_user.organization_id is None
    )
    case_query = select(func.count(Case.id)).where(
        Case.status.in_([CaseStatus.new, CaseStatus.verified]),
        Case.urgency_level.in_([UrgencyLevel.critical, UrgencyLevel.high]),
    )
    if not is_global_super_admin:
        case_query = case_query.where(Case.organization_id == current_user.organization_id)
    unassigned_count = db.execute(case_query).scalar()

    volunteer_query = select(func.count(Volunteer.id)).where(
        Volunteer.availability_status == AvailabilityStatus.available,
        Volunteer.active_assignment_count == 0,
    )
    if not is_global_super_admin:
        volunteer_query = volunteer_query.where(Volunteer.organization_id == current_user.organization_id)
    idle_count = db.execute(volunteer_query).scalar()

    return {
        "success": True,
        "data": {
            "unassigned_urgent_cases": unassigned_count,
            "idle_volunteers": idle_count,
            "recommendation": (
                "Match idle volunteers to unassigned urgent cases immediately."
                if unassigned_count > 0 and idle_count > 0
                else "Resource distribution appears balanced."
            ),
        },
    }
