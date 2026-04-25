"""app/schemas/case.py — Case CRUD and action schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import (
    CaseCategory,
    CaseStatus,
    DisasterType,
    SourceType,
    UrgencyLevel,
    VerificationStatus,
)
from app.schemas.common import HopeAidBase


class ResourceNeededItem(HopeAidBase):
    item: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class CaseCreate(HopeAidBase):
    household_id: Optional[UUID] = None
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    category: CaseCategory
    subcategory: Optional[str] = Field(None, max_length=100)
    urgency_level: UrgencyLevel = UrgencyLevel.medium
    disaster_type: Optional[DisasterType] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    situation_type: Optional[str] = None
    special_requirements: Optional[str] = None
    resource_needed: Optional[list[ResourceNeededItem]] = None
    number_of_people_affected: int = Field(1, ge=1)
    source_type: SourceType = SourceType.manual
    confidence_score: Optional[float] = Field(None, ge=0, le=100)
    ai_extraction_id: Optional[UUID] = None


class CaseUpdate(HopeAidBase):
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    category: Optional[CaseCategory] = None
    subcategory: Optional[str] = None
    urgency_level: Optional[UrgencyLevel] = None
    disaster_type: Optional[DisasterType] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    situation_type: Optional[str] = None
    special_requirements: Optional[str] = None
    resource_needed: Optional[list[ResourceNeededItem]] = None
    number_of_people_affected: Optional[int] = Field(None, ge=1)


class CaseRejectRequest(HopeAidBase):
    reason: str = Field(..., min_length=5)


class CaseAssignRequest(HopeAidBase):
    volunteer_id: UUID
    notes: Optional[str] = None


class CaseOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    household_id: Optional[UUID]
    reporter_user_id: Optional[UUID]
    case_number: str
    title: str
    description: Optional[str]
    category: CaseCategory
    subcategory: Optional[str]
    urgency_level: UrgencyLevel
    risk_score: Optional[float]
    disaster_type: Optional[DisasterType]
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    situation_type: Optional[str]
    special_requirements: Optional[str]
    resource_needed: Optional[list[Any]]
    number_of_people_affected: int
    status: CaseStatus
    verification_status: VerificationStatus
    source_type: SourceType
    confidence_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]


class DuplicateCheckResult(HopeAidBase):
    is_duplicate: bool
    confidence: float  # 0-100
    matched_cases: list[dict[str, Any]]
    explanation: str
