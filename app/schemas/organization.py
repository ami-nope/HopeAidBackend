"""app/schemas/organization.py — Organization CRUD schemas."""

from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import OrgStatus
from app.schemas.common import HopeAidBase


class OrgCreate(HopeAidBase):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9\-]+$")
    status: OrgStatus = OrgStatus.pending
    settings_json: Optional[dict[str, Any]] = None


class OrgUpdate(HopeAidBase):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    status: Optional[OrgStatus] = None
    settings_json: Optional[dict[str, Any]] = None


class OrgOut(HopeAidBase):
    id: UUID
    name: str
    slug: str
    status: OrgStatus
    settings_json: Optional[dict[str, Any]]
