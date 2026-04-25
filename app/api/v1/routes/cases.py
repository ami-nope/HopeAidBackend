"""app/api/v1/routes/cases.py — Case management endpoints. All sync."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_roles
from app.core.constants import APPROVERS, CaseStatus, UserRole
from app.db.session import get_db
from app.models.user import User
from app.schemas.case import (
    CaseAssignRequest,
    CaseCreate,
    CaseOut,
    CaseRejectRequest,
    CaseUpdate,
    DuplicateCheckResult,
)
from app.schemas.common import APIResponse, PaginatedResponse
from app.services.case_service import CaseService
from app.utils.pagination import build_pagination_meta, get_pagination, PaginationParams

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=APIResponse[CaseOut], status_code=201)
def create_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new aid case. Risk score is auto-computed."""
    try:
        service = CaseService(db, current_user)
        case = service.create_case(data)
        db.commit()
        db.refresh(case)
        return {"success": True, "data": CaseOut.model_validate(case)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("", response_model=PaginatedResponse[CaseOut])
def list_cases(
    status: Optional[CaseStatus] = Query(None),
    urgency: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List cases for the current user's organization with optional filters."""
    service = CaseService(db, current_user)
    cases, total = service.list_cases(
        status=status,
        urgency=urgency,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return {
        "success": True,
        "data": [CaseOut.model_validate(c) for c in cases],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.get("/{case_id}", response_model=APIResponse[CaseOut])
def get_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db, current_user)
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return {"success": True, "data": CaseOut.model_validate(case)}


@router.put("/{case_id}", response_model=APIResponse[CaseOut])
def update_case(
    case_id: UUID,
    data: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        service = CaseService(db, current_user)
        case = service.update_case(case_id, data)
        db.commit()
        db.refresh(case)
        return {"success": True, "data": CaseOut.model_validate(case)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{case_id}", response_model=APIResponse[None])
def delete_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.super_admin, UserRole.admin, UserRole.org_manager)),
):
    """Soft-delete: sets case status to rejected."""
    service = CaseService(db, current_user)
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    case.status = CaseStatus.rejected
    db.commit()
    return {"success": True, "message": "Case deleted"}


@router.post("/{case_id}/approve", response_model=APIResponse[CaseOut])
def approve_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPROVERS)),
):
    """Approve (verify) a case. Requires reviewer, org_manager, admin, or super_admin."""
    try:
        service = CaseService(db, current_user)
        case = service.approve_case(case_id)
        db.commit()
        db.refresh(case)
        return {"success": True, "data": CaseOut.model_validate(case)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{case_id}/reject", response_model=APIResponse[CaseOut])
def reject_case(
    case_id: UUID,
    request: CaseRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPROVERS)),
):
    """Reject a case with a reason."""
    try:
        service = CaseService(db, current_user)
        case = service.reject_case(case_id, request)
        db.commit()
        db.refresh(case)
        return {"success": True, "data": CaseOut.model_validate(case)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{case_id}/close", response_model=APIResponse[CaseOut])
def close_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*APPROVERS)),
):
    """Close a case that is in_progress, assigned, or resolved."""
    try:
        service = CaseService(db, current_user)
        case = service.close_case(case_id)
        db.commit()
        db.refresh(case)
        return {"success": True, "data": CaseOut.model_validate(case)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{case_id}/assign", response_model=APIResponse[None])
def assign_volunteer(
    case_id: UUID,
    request: CaseAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.admin, UserRole.org_manager, UserRole.field_coordinator, UserRole.super_admin
    )),
):
    """Directly assign a volunteer to a case."""
    from app.models.assignment import Assignment
    from app.core.constants import AssignmentStatus

    service = CaseService(db, current_user)
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    assignment = Assignment(
        case_id=case.id,
        volunteer_id=request.volunteer_id,
        assigned_by_user_id=current_user.id,
        organization_id=current_user.organization_id,
        status=AssignmentStatus.pending,
        notes=request.notes,
    )
    db.add(assignment)
    case.status = CaseStatus.assigned
    db.commit()
    return {"success": True, "message": "Volunteer assigned successfully"}


@router.post("/{case_id}/recalculate-risk", response_model=APIResponse[CaseOut])
def recalculate_risk(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recompute risk score including vulnerability data from linked persons."""
    try:
        service = CaseService(db, current_user)
        case = service.recalculate_risk(case_id)
        db.commit()
        db.refresh(case)
        return {"success": True, "data": CaseOut.model_validate(case)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{case_id}/duplicate-check", response_model=APIResponse[DuplicateCheckResult])
def check_duplicate(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run fuzzy duplicate detection for this case against recent org cases."""
    try:
        service = CaseService(db, current_user)
        result = service.check_duplicate(case_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(400, str(e))
