"""app/schemas/audit_log.py — Audit log output schema."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.schemas.common import HopeAidBase


class AuditLogOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    actor_user_id: Optional[UUID]
    action_type: str
    entity_type: str
    entity_id: UUID
    before_json: Optional[dict[str, Any]]
    after_json: Optional[dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime
