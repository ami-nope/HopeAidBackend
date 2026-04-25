"""app/schemas/volunteer.py — Volunteer and availability schemas."""

from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field

from app.core.constants import AvailabilityStatus, DutyType
from app.schemas.common import HopeAidBase


class VolunteerCreate(HopeAidBase):
    name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr] = None
    current_location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    skills: Optional[list[str]] = []
    languages: Optional[list[str]] = []
    has_transport: bool = False
    has_medical_training: bool = False
    vehicle_type: Optional[str] = None
    duty_type: DutyType = DutyType.on_call
    availability_status: AvailabilityStatus = AvailabilityStatus.available
    user_id: Optional[UUID] = None  # Link to existing user account


class VolunteerUpdate(HopeAidBase):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    current_location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    skills: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    has_transport: Optional[bool] = None
    has_medical_training: Optional[bool] = None
    vehicle_type: Optional[str] = None
    duty_type: Optional[DutyType] = None
    availability_status: Optional[AvailabilityStatus] = None


class VolunteerOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    user_id: Optional[UUID]
    name: str
    phone: Optional[str]
    email: Optional[str]
    current_location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    skills: Optional[list[str]]
    languages: Optional[list[str]]
    has_transport: bool
    has_medical_training: bool
    vehicle_type: Optional[str]
    duty_type: DutyType
    reliability_score: float
    availability_status: AvailabilityStatus
    active_assignment_count: int


class AvailabilitySlotCreate(HopeAidBase):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    status: str = "available"
    notes: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None


class AvailabilitySlotOut(HopeAidBase):
    id: UUID
    volunteer_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    status: str
    notes: Optional[str]
    valid_from: Optional[date]
    valid_until: Optional[date]
