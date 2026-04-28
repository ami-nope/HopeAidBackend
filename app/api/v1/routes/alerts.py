"""app/api/v1/routes/alerts.py — Alert and reminder endpoints. All sync."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import AlertType, RecipientType, UserRole
from app.api.v1.deps import get_current_user, require_permissions
from app.core.constants import AlertStatus
from app.db.session import get_db
from app.models.alert import Alert
from app.models.case import Case
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertOut
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.weather_intelligence import WeatherBatchRunOut
from app.services.weather_intelligence_service import WeatherIntelligenceService
from app.utils.pagination import PaginationParams, build_pagination_meta, get_pagination

router = APIRouter(tags=["Alerts & Reminders"])


@router.post("/alerts", response_model=APIResponse[AlertOut], status_code=201)
def create_alert(
    data: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:create")),
):
    org_id = current_user.organization_id
    if org_id is None:
        raise HTTPException(400, "organization_id is required for alert creation")

    alert = Alert(
        organization_id=org_id,
        **data.model_dump(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {"success": True, "data": AlertOut.model_validate(alert)}


@router.get("/alerts", response_model=PaginatedResponse[AlertOut])
def list_alerts(
    pagination: PaginationParams = Depends(get_pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:view")),
):
    q = select(Alert).where(Alert.status == AlertStatus.active)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Alert.organization_id == current_user.organization_id)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    alerts = db.execute(
        q.order_by(Alert.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    ).scalars().all()
    return {
        "success": True,
        "data": [AlertOut.model_validate(a) for a in alerts],
        "meta": build_pagination_meta(total, pagination.page, pagination.page_size),
    }


@router.post("/alerts/{alert_id}/resolve", response_model=APIResponse[AlertOut])
def resolve_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:resolve")),
):
    q = select(Alert).where(Alert.id == alert_id)
    if not (current_user.role == UserRole.super_admin and current_user.organization_id is None):
        q = q.where(Alert.organization_id == current_user.organization_id)
    alert = db.execute(q).scalars().first()
    if not alert:
        raise HTTPException(404, "Alert not found")

    alert.status = AlertStatus.resolved
    alert.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(alert)
    return {"success": True, "data": AlertOut.model_validate(alert)}


@router.post("/alerts/intelligence/run", response_model=APIResponse[WeatherBatchRunOut])
def run_weather_intelligence_inline(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:create")),
):
    service = WeatherIntelligenceService(db)
    result = service.scan_due_cases(current_user.organization_id)
    db.commit()
    return {"success": True, "data": WeatherBatchRunOut(**result)}


@router.post("/alerts/intelligence/simulate", response_model=APIResponse[AlertOut], status_code=201)
def simulate_weather_alert(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("alerts:create")),
):
    org_id = current_user.organization_id
    if org_id is None:
        raise HTTPException(400, "organization_id is required for alert simulation")

    case = db.execute(
        select(Case)
        .where(Case.organization_id == org_id)
        .order_by(Case.created_at.desc())
        .limit(1)
    ).scalars().first()

    location_label = None
    if case:
        location_label = case.location_name or case.title
    location_label = location_label or "the active response area"

    message = f"Simulation: heavy rain may disrupt volunteers near {location_label}"
    metadata = {
        "simulation": True,
        "heading": f"Simulated weather risk near {location_label}",
        "description": "Heavy rain and wind may slow volunteer movement and delay relief delivery.",
        "full_text": (
            f"This simulated alert tests the weather intelligence pipeline for {location_label}. "
            "Use it to confirm alert rendering, expansion, and admin workflows."
        ),
        "solution": "Delay volunteer dispatch by 30 minutes, verify road access, and contact the affected households.",
        "severity": "high",
        "danger_for_community": True,
        "can_be_solved": True,
        "danger_on_volunteers": True,
        "providers": {
            "forecast_provider": "simulation",
            "warning_provider": "simulation",
            "model_used": "simulation",
        },
    }

    alert = db.execute(
        select(Alert).where(
            Alert.organization_id == org_id,
            Alert.type == AlertType.weather_risk,
            Alert.status == AlertStatus.active,
            Alert.message == message,
        )
    ).scalars().first()

    if alert:
        alert.case_id = case.id if case else None
        alert.recipient_type = RecipientType.admin
        alert.metadata_json = metadata
    else:
        alert = Alert(
            organization_id=org_id,
            case_id=case.id if case else None,
            type=AlertType.weather_risk,
            message=message,
            recipient_type=RecipientType.admin,
            metadata_json=metadata,
        )
        db.add(alert)

    db.commit()
    db.refresh(alert)
    return {"success": True, "data": AlertOut.model_validate(alert)}


@router.post("/reminders/run", response_model=APIResponse[dict])
def run_reminders(
    current_user: User = Depends(require_permissions("alerts:create")),
):
    """Manually trigger the reminder/alert check Celery tasks."""
    from app.workers.tasks.ai_tasks import check_unassigned_critical_cases, check_inventory_health
    from app.workers.tasks.weather_tasks import scan_due_weather_cases
    check_unassigned_critical_cases.delay()
    check_inventory_health.delay()
    scan_due_weather_cases.delay()
    return {"success": True, "data": {"message": "Reminder tasks queued"}}
