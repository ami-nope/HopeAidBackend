"""app/schemas/auth.py — Auth request/response schemas."""

from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.constants import UserRole
from app.schemas.common import HopeAidBase
from app.utils.contact import sanitize_placeholder_email


class RegisterRequest(HopeAidBase):
    organization_id: UUID
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.field_coordinator

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(HopeAidBase):
    identifier: str = Field(..., min_length=3, max_length=320)
    password: str

    @model_validator(mode="before")
    @classmethod
    def resolve_identifier_aliases(cls, data):
        if isinstance(data, dict):
            value = data.get("identifier") or data.get("email") or data.get("phone")
            if value is not None:
                payload = dict(data)
                payload["identifier"] = value
                return payload
        return data

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("identifier is required")
        return cleaned


class TokenResponse(HopeAidBase):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(HopeAidBase):
    refresh_token: str


class UserOut(HopeAidBase):
    id: UUID
    organization_id: Optional[UUID]
    name: str
    email: Optional[str]
    phone: Optional[str]
    role: UserRole
    is_active: bool

    @field_validator("email", mode="before")
    @classmethod
    def hide_placeholder_email(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_placeholder_email(value)


class MeResponse(HopeAidBase):
    user: UserOut
    organization_name: Optional[str] = None
    role_label: Optional[str] = None
    permissions: list[str] = []
