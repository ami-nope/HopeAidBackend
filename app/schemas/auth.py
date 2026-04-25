"""app/schemas/auth.py — Auth request/response schemas."""

from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.core.constants import UserRole
from app.schemas.common import HopeAidBase


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
    email: EmailStr
    password: str


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
    email: str
    phone: Optional[str]
    role: UserRole
    is_active: bool


class MeResponse(HopeAidBase):
    user: UserOut
    organization_name: Optional[str] = None
