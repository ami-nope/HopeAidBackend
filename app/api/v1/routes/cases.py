"""app/api/v1/routes/cases.py — Case management endpoints. All sync."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permissions
from app.core.constants import CaseStatus
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
from app.schemas.weather_intelligence import (
    CaseLocationRefreshOut,
    WeatherBatchRunOut,
    WeatherIntelligenceRunOut,
)
from app.services.case_service import CaseService
from app.services.weather_intelligence_service import WeatherIntelligenceService
from app.utils.pagination import build_pagination_meta, get_pagination, PaginationParams

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=APIResponse[CaseOut], status_code=201)
def create_case(
    data: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:create")),
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
    q: Optional[str] = Query(None, min_length=1),
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:view")),
):
    """List cases for the current user's organization with optional filters."""
    service = CaseService(db, current_user)
    cases, total = service.list_cases(
        status=status,
        urgency=urgency,
        q=q,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return {
        "success": True,
        "data": [CaseOut.model_validate(c) for c in cases],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.post("/weather-intelligence/run", response_model=APIResponse[WeatherBatchRunOut])
def run_weather_intelligence_batch(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:create")),
):
    service = WeatherIntelligenceService(db)
    result = service.scan_due_cases(current_user.organization_id)
    db.commit()
    return {"success": True, "data": WeatherBatchRunOut(**result)}


@router.get("/assigned/me", response_model=PaginatedResponse[CaseOut])
def list_my_assigned_cases(
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:view")),
):
    from app.core.constants import UserRole
    from app.models.assignment import Assignment
    from app.models.volunteer import Volunteer

    query = (
        select(Case)
        .join(Assignment, Assignment.case_id == Case.id)
        .join(Volunteer, Volunteer.id == Assignment.volunteer_id)
        .where(Volunteer.user_id == current_user.id)
    )
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        query = query.where(Case.organization_id == current_user.organization_id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    cases = db.execute(
        query.order_by(Case.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    ).scalars().all()
    return {
        "success": True,
        "data": [CaseOut.model_validate(c) for c in cases],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.post("/{case_id}/refresh-location", response_model=APIResponse[CaseLocationRefreshOut])
def refresh_case_location(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:update")),
):
    service = CaseService(db, current_user)
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    intelligence = WeatherIntelligenceService(db)
    intelligence.refresh_case_location(case)
    db.commit()
    db.refresh(case)
    return {
        "success": True,
        "data": CaseLocationRefreshOut(
            case_id=case.id,
            geocode_status=case.geocode_status,
            latitude=float(case.latitude) if case.latitude is not None else None,
            longitude=float(case.longitude) if case.longitude is not None else None,
            district=case.district,
            state=case.state,
            geocode_provider=case.geocode_provider,
            geocode_confidence=float(case.geocode_confidence) if case.geocode_confidence is not None else None,
        ),
    }


@router.post("/{case_id}/weather-intelligence", response_model=APIResponse[WeatherIntelligenceRunOut])
def run_case_weather_intelligence(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:create")),
):
    service = CaseService(db, current_user)
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    intelligence = WeatherIntelligenceService(db)
    result = intelligence.run_case_monitor(case)
    db.commit()
    db.refresh(case)

    return {
        "success": True,
        "data": WeatherIntelligenceRunOut(
            case_id=case.id,
            geocode_status=case.geocode_status,
            weather_risk_band=case.weather_risk_band,
            last_weather_checked_at=case.last_weather_checked_at,
            next_weather_check_at=case.next_weather_check_at,
            snapshot=(
                None
                if not result.snapshot
                else {
                    "id": result.snapshot.id,
                    "case_id": result.snapshot.case_id,
                    "forecast_provider": result.snapshot.forecast_provider,
                    "warning_provider": result.snapshot.warning_provider,
                    "latitude": float(result.snapshot.latitude),
                    "longitude": float(result.snapshot.longitude),
                    "location_label": result.snapshot.location_label,
                    "collected_at": result.snapshot.collected_at,
                    "forecast_window_end": result.snapshot.forecast_window_end,
                    "summary_json": result.snapshot.summary_json,
                }
            ),
            assessment=(
                None
                if not result.assessment
                else {
                    "id": result.assessment.id,
                    "case_id": result.assessment.case_id,
                    "weather_snapshot_id": result.assessment.weather_snapshot_id,
                    "risk_band": result.assessment.risk_band,
                    "severity": result.assessment.severity,
                    "hazard_score": float(result.assessment.hazard_score),
                    "danger_for_community": result.assessment.danger_for_community,
                    "can_be_solved": result.assessment.can_be_solved,
                    "danger_on_volunteers": result.assessment.danger_on_volunteers,
                    "heading": result.assessment.heading,
                    "description": result.assessment.description,
                    "full_text": result.assessment.full_text,
                    "solution": result.assessment.solution,
                    "reason_codes_json": result.assessment.reason_codes_json,
                    "factors_json": result.assessment.factors_json,
                    "providers_json": result.assessment.providers_json,
                    "model_used": result.assessment.model_used,
                    "prompt_version": result.assessment.prompt_version,
                    "alert_emitted": result.assessment.alert_emitted,
                    "created_at": result.assessment.created_at,
                    "updated_at": result.assessment.updated_at,
                }
            ),
        ),
    }


@router.get("/{case_id}", response_model=APIResponse[CaseOut])
def get_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("cases:view")),
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
    current_user: User = Depends(require_permissions("cases:update")),
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
    current_user: User = Depends(require_permissions("cases:delete")),
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
    current_user: User = Depends(require_permissions("cases:approve")),
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
    current_user: User = Depends(require_permissions("cases:approve")),
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
    current_user: User = Depends(require_permissions("cases:close")),
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
    current_user: User = Depends(require_permissions("cases:assign")),
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
        organization_id=case.organization_id,
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
    current_user: User = Depends(require_permissions("cases:update")),
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
    current_user: User = Depends(require_permissions("cases:view")),
):
    """Run fuzzy duplicate detection for this case against recent org cases."""
    try:
        service = CaseService(db, current_user)
        result = service.check_duplicate(case_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(400, str(e))
