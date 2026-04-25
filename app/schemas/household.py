"""app/schemas/household.py — Household and Person CRUD schemas."""

from typing import Any, Optional
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import HopeAidBase


class HouseholdCreate(HopeAidBase):
    household_name: str = Field(..., min_length=1, max_length=255)
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[EmailStr] = None
    vulnerability_flags: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class HouseholdUpdate(HopeAidBase):
    household_name: Optional[str] = Field(None, min_length=1, max_length=255)
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    vulnerability_flags: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class HouseholdOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    household_name: str
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    contact_name: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    vulnerability_flags: Optional[dict[str, Any]]
    notes: Optional[str]
    person_count: Optional[int] = None  # Computed field, populated in service
