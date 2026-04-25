"""
app/services/audit_service.py — Audit log creation helper.

Called from all services after any data-mutating operation.
Creates immutable audit trail entries — never modifies them.

Synchronous — no async, no await.
"""

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    organization_id: uuid.UUID,
    actor_user_id: Optional[uuid.UUID],
    action_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    before_json: Optional[dict[str, Any]] = None,
    after_json: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Create an audit log entry for a significant state change.

    Args:
        db            — active DB session (caller must commit)
        organization_id — org scope (multi-tenancy)
        actor_user_id — who did this action
        action_type   — verb, e.g. "CASE_CREATED", "CASE_APPROVED"
        entity_type   — table name, e.g. "case", "volunteer"
        entity_id     — UUID of the affected row
        before_json   — state before change (None for creates)
        after_json    — state after change (None for deletes)
        ip_address    — request IP for security audit trails
    """
    log = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before_json,
        after_json=after_json,
        ip_address=ip_address,
    )
    # Add to session — caller is responsible for commit
    db.add(log)
