"""app/schemas/report.py — Report job schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID


from app.core.constants import ReportFormat, ReportStatus, ReportType
from app.schemas.common import HopeAidBase


class ReportJobCreate(HopeAidBase):
    report_type: ReportType
    filters_json: Optional[dict[str, Any]] = None
    format: ReportFormat = ReportFormat.csv


class ReportJobOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    requested_by_user_id: Optional[UUID]
    report_type: ReportType
    filters_json: Optional[dict[str, Any]]
    output_url: Optional[str]
    format: ReportFormat
    status: ReportStatus
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class DashboardSummary(HopeAidBase):
    total_cases: int
    open_cases: int
    critical_cases: int
    total_volunteers: int
    available_volunteers: int
    total_households: int
    low_stock_items: int
    active_alerts: int
    cases_by_status: dict[str, int]
    cases_by_category: dict[str, int]
    recent_cases: list[dict[str, Any]]


class AllocationRecommendation(HopeAidBase):
    volunteer_id: UUID
    volunteer_name: str
    allocation_score: float
    reasoning: dict[str, Any]
    explanation: str  # Human-readable LLM explanation


class AllocationRecommendResponse(HopeAidBase):
    case_id: UUID
    recommendations: list[AllocationRecommendation]
    conflict_warnings: list[str]
