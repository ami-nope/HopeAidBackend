"""app/models/alert.py — Alert / notification model."""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import AlertStatus, AlertType, RecipientType
from app.db.base import Base, UUIDMixin


class Alert(UUIDMixin, Base):
    """
    System-generated or manual alerts for org administrators.
    Examples: urgent unassigned case, inventory low, volunteer overloaded.
    """

    __tablename__ = "alerts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[AlertType] = mapped_column(
        SAEnum(AlertType, name="alert_type_enum"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, name="alert_status_enum"),
        default=AlertStatus.active,
        nullable=False,
        index=True,
    )
    recipient_type: Mapped[RecipientType] = mapped_column(
        SAEnum(RecipientType, name="recipient_type_enum"),
        default=RecipientType.admin,
        nullable=False,
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Alert id={self.id} type={self.type} status={self.status}>"
