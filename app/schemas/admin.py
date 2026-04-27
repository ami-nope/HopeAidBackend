"""app/schemas/admin.py - Admin-specific request schemas."""

from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.constants import UserRole
from app.schemas.common import HopeAidBase


class AdminUserCreate(HopeAidBase):
    organization_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    identifier: Optional[str] = Field(None, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    create_volunteer_profile: bool = False

    @model_validator(mode="before")
    @classmethod
    def resolve_identifier_alias(cls, data):
        if isinstance(data, dict):
            payload = dict(data)
            identifier = payload.get("identifier")
            email = payload.get("email")
            phone = payload.get("phone")
            if identifier and not email and not phone:
                identifier_text = str(identifier).strip()
                if "@" in identifier_text:
                    payload["email"] = identifier_text
                else:
                    payload["phone"] = identifier_text
            return payload
        return data

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not (self.phone and self.phone.strip()):
            raise ValueError("Either email or phone is required")
        return self

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
