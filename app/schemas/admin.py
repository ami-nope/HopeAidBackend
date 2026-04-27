"""app/schemas/admin.py - Admin-specific request schemas."""

from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.core.constants import UserRole
from app.schemas.common import HopeAidBase


class AdminUserCreate(HopeAidBase):
    organization_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    create_volunteer_profile: bool = False

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
