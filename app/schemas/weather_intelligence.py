"""Schemas for weather intelligence responses."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.core.constants import GeocodeStatus, WeatherRiskBand
from app.schemas.common import HopeAidBase


class WeatherDecisionOut(HopeAidBase):
    danger_for_community: bool
    can_be_solved: bool
    danger_on_volunteers: bool


class WeatherSnapshotOut(HopeAidBase):
    id: UUID
    case_id: UUID
    forecast_provider: str
    warning_provider: Optional[str]
    latitude: float
    longitude: float
    location_label: Optional[str]
    collected_at: datetime
    forecast_window_end: Optional[datetime]
    summary_json: dict[str, Any]


class HazardAssessmentOut(HopeAidBase):
    id: UUID
    case_id: UUID
    weather_snapshot_id: Optional[UUID]
    risk_band: WeatherRiskBand
    severity: str
    hazard_score: float
    danger_for_community: bool
    can_be_solved: bool
    danger_on_volunteers: bool
    heading: Optional[str]
    description: Optional[str]
    full_text: Optional[str]
    solution: Optional[str]
    reason_codes_json: dict[str, Any]
    factors_json: dict[str, Any]
    providers_json: dict[str, Any]
    model_used: Optional[str]
    prompt_version: Optional[str]
    alert_emitted: bool
    created_at: datetime
    updated_at: datetime


class CaseLocationRefreshOut(HopeAidBase):
    case_id: UUID
    geocode_status: GeocodeStatus
    latitude: Optional[float]
    longitude: Optional[float]
    district: Optional[str]
    state: Optional[str]
    geocode_provider: Optional[str]
    geocode_confidence: Optional[float]


class WeatherIntelligenceRunOut(HopeAidBase):
    case_id: UUID
    geocode_status: GeocodeStatus
    weather_risk_band: Optional[WeatherRiskBand]
    last_weather_checked_at: Optional[datetime]
    next_weather_check_at: Optional[datetime]
    snapshot: Optional[WeatherSnapshotOut] = None
    assessment: Optional[HazardAssessmentOut] = None


class WeatherBatchRunOut(HopeAidBase):
    scanned_cases: int
    assessed_cases: int
    alerts_created_or_updated: int
    alerts_resolved: int
    geocoded_cases: int
    skipped_cases: int
