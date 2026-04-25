"""app/schemas/person.py — Person / beneficiary schemas."""

from typing import Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import Gender
from app.schemas.common import HopeAidBase


class PersonCreate(HopeAidBase):
    household_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    relation_to_head: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    special_needs: Optional[str] = None
    has_children: bool = False
    is_pregnant: bool = False
    has_disability: bool = False
    medical_notes: Optional[str] = None
    photo_url: Optional[str] = None
    id_proof_url: Optional[str] = None


class PersonUpdate(HopeAidBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[Gender] = None
    relation_to_head: Optional[str] = None
    phone: Optional[str] = None
    special_needs: Optional[str] = None
    has_children: Optional[bool] = None
    is_pregnant: Optional[bool] = None
    has_disability: Optional[bool] = None
    medical_notes: Optional[str] = None
    photo_url: Optional[str] = None
    id_proof_url: Optional[str] = None


class PersonOut(HopeAidBase):
    id: UUID
    household_id: UUID
    organization_id: UUID
    name: str
    age: Optional[int]
    gender: Optional[Gender]
    relation_to_head: Optional[str]
    phone: Optional[str]
    special_needs: Optional[str]
    has_children: bool
    is_pregnant: bool
    has_disability: bool
    medical_notes: Optional[str]
    photo_url: Optional[str]
    id_proof_url: Optional[str]
