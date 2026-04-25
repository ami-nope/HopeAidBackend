"""app/schemas/assignment.py — Assignment schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import AssignmentStatus
from app.schemas.common import HopeAidBase


class AssignmentCreate(HopeAidBase):
    case_id: UUID
    volunteer_id: UUID
    notes: Optional[str] = None
    allocation_score: Optional[float] = Field(None, ge=0, le=100)
    reasoning: Optional[dict[str, Any]] = None


class AssignmentStatusUpdate(HopeAidBase):
    status: AssignmentStatus
    notes: Optional[str] = None


class AssignmentOut(HopeAidBase):
    id: UUID
    case_id: UUID
    volunteer_id: UUID
    assigned_by_user_id: Optional[UUID]
    organization_id: UUID
    status: AssignmentStatus
    allocation_score: Optional[float]
    reasoning: Optional[dict[str, Any]]
    notes: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
