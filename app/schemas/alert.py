"""app/schemas/alert.py — Alert and notification schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import AlertStatus, AlertType, RecipientType
from app.schemas.common import HopeAidBase


class AlertCreate(HopeAidBase):
    case_id: Optional[UUID] = None
    type: AlertType
    message: str = Field(..., min_length=3)
    recipient_type: RecipientType = RecipientType.admin
    metadata_json: Optional[dict[str, Any]] = None


class AlertOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    case_id: Optional[UUID]
    type: AlertType
    message: str
    status: AlertStatus
    recipient_type: RecipientType
    metadata_json: Optional[dict[str, Any]]
    created_at: datetime
    resolved_at: Optional[datetime]
