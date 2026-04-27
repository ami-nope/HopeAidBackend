"""app/api/v1/routes/reports.py — Dashboard, reports, and export endpoints. All sync."""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permissions
from app.core.constants import UserRole
from app.db.session import get_db
from app.models.alert import Alert
from app.models.case import Case
from app.models.household import Household
from app.models.inventory import InventoryItem
from app.models.user import User
from app.models.volunteer import Volunteer
from app.schemas.common import APIResponse
from app.schemas.report import DashboardSummary

router = APIRouter(tags=["Reports & Exports"])


def _apply_org_scope(query, model, current_user: User):
    if current_user.role == UserRole.super_admin and current_user.organization_id is None:
        return query
    return query.where(model.organization_id == current_user.organization_id)


@router.get("/dashboard/summary", response_model=APIResponse[DashboardSummary])
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    """Organization dashboard summary metrics."""
    from app.core.constants import CaseStatus, UrgencyLevel, AvailabilityStatus, AlertStatus, InventoryStatus

    total_cases = db.execute(
        _apply_org_scope(select(func.count(Case.id)), Case, current_user)
    ).scalar()
    open_cases = db.execute(_apply_org_scope(select(func.count(Case.id)).where(
        Case.status.in_([CaseStatus.new, CaseStatus.verified, CaseStatus.assigned, CaseStatus.in_progress]),
    ), Case, current_user)).scalar()
    critical_cases = db.execute(_apply_org_scope(select(func.count(Case.id)).where(
        Case.urgency_level == UrgencyLevel.critical,
        Case.status != CaseStatus.closed,
    ), Case, current_user)).scalar()
    total_volunteers = db.execute(
        _apply_org_scope(select(func.count(Volunteer.id)), Volunteer, current_user)
    ).scalar()
    available_volunteers = db.execute(_apply_org_scope(select(func.count(Volunteer.id)).where(
        Volunteer.availability_status == AvailabilityStatus.available,
    ), Volunteer, current_user)).scalar()
    total_households = db.execute(
        _apply_org_scope(select(func.count(Household.id)), Household, current_user)
    ).scalar()
    low_stock = db.execute(_apply_org_scope(select(func.count(InventoryItem.id)).where(
        InventoryItem.status.in_([InventoryStatus.low_stock, InventoryStatus.out_of_stock]),
    ), InventoryItem, current_user)).scalar()
    active_alerts = db.execute(_apply_org_scope(select(func.count(Alert.id)).where(
        Alert.status == AlertStatus.active,
    ), Alert, current_user)).scalar()

    # Cases by status
    status_result = db.execute(
        _apply_org_scope(
            select(Case.status, func.count(Case.id)).group_by(Case.status),
            Case,
            current_user,
        )
    )
    cases_by_status = {row[0].value: row[1] for row in status_result}

    # Cases by category
    cat_result = db.execute(
        _apply_org_scope(
            select(Case.category, func.count(Case.id)).group_by(Case.category),
            Case,
            current_user,
        )
    )
    cases_by_category = {row[0].value: row[1] for row in cat_result}

    # Recent 5 cases
    recent_cases = [
        {
            "id": str(c.id),
            "case_number": c.case_number,
            "title": c.title,
            "urgency": c.urgency_level.value,
            "status": c.status.value,
        }
        for c in db.execute(
            _apply_org_scope(
                select(Case).order_by(Case.created_at.desc()).limit(5),
                Case,
                current_user,
            )
        ).scalars()
    ]

    return {
        "success": True,
        "data": DashboardSummary(
            total_cases=total_cases,
            open_cases=open_cases,
            critical_cases=critical_cases,
            total_volunteers=total_volunteers,
            available_volunteers=available_volunteers,
            total_households=total_households,
            low_stock_items=low_stock,
            active_alerts=active_alerts,
            cases_by_status=cases_by_status,
            cases_by_category=cases_by_category,
            recent_cases=recent_cases,
        ),
    }


@router.get("/reports/cases", response_model=APIResponse[dict])
def report_cases(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    """Summary report of cases with optional status filter."""
    q = _apply_org_scope(select(Case), Case, current_user)
    if status:
        q = q.where(Case.status == status)
    cases = [
        {
            "case_number": c.case_number,
            "title": c.title,
            "category": c.category.value,
            "urgency": c.urgency_level.value,
            "status": c.status.value,
            "risk_score": float(c.risk_score) if c.risk_score else None,
            "people_affected": c.number_of_people_affected,
            "location": c.location_name,
        }
        for c in db.execute(q.order_by(Case.created_at.desc()).limit(200)).scalars()
    ]
    return {"success": True, "data": {"cases": cases, "count": len(cases)}}


@router.get("/reports/volunteers", response_model=APIResponse[dict])
def report_volunteers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    volunteers = [
        {
            "name": v.name,
            "skills": v.skills or [],
            "availability": v.availability_status.value,
            "reliability_score": float(v.reliability_score),
            "active_assignments": v.active_assignment_count,
        }
        for v in db.execute(
            _apply_org_scope(select(Volunteer), Volunteer, current_user)
        ).scalars()
    ]
    return {"success": True, "data": {"volunteers": volunteers, "count": len(volunteers)}}


@router.get("/reports/inventory", response_model=APIResponse[dict])
def report_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    items = [
        {
            "item_name": i.item_name,
            "item_type": i.item_type.value,
            "quantity": float(i.quantity),
            "unit": i.unit,
            "status": i.status.value,
            "location": i.location_name,
        }
        for i in db.execute(
            _apply_org_scope(select(InventoryItem), InventoryItem, current_user)
        ).scalars()
    ]
    return {"success": True, "data": {"items": items, "count": len(items)}}


@router.get("/exports/cases.csv")
def export_cases_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    """Stream cases as a CSV download."""
    cases = db.execute(
        _apply_org_scope(
            select(Case).order_by(Case.created_at.desc()),
            Case,
            current_user,
        )
    ).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "case_number", "title", "category", "urgency_level", "status",
        "risk_score", "number_of_people_affected", "location_name",
        "disaster_type", "created_at",
    ])
    for c in cases:
        writer.writerow([
            c.case_number, c.title, c.category.value, c.urgency_level.value,
            c.status.value, str(c.risk_score or ""), c.number_of_people_affected,
            c.location_name or "", c.disaster_type.value if c.disaster_type else "",
            c.created_at.isoformat(),
        ])

    filename = f"cases_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/exports/cases.pdf")
def export_cases_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports:view")),
):
    """Export cases as a PDF report using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    cases = db.execute(
        _apply_org_scope(
            select(Case).order_by(Case.created_at.desc()).limit(100),
            Case,
            current_user,
        )
    ).scalars().all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("HopeAid - Cases Report", styles["Title"])]

    data = [["Case #", "Title", "Category", "Urgency", "Status", "People"]]
    for c in cases:
        data.append([
            c.case_number, c.title[:40], c.category.value,
            c.urgency_level.value, c.status.value, str(c.number_of_people_affected),
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    doc.build(elements)

    filename = f"cases_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
