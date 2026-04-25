"""app/models/assignment.py — Case-to-volunteer assignment model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AssignmentStatus
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.volunteer import Volunteer
    from app.models.user import User


class Assignment(UUIDMixin, TimestampMixin, Base):
    """
    Links a case to a volunteer. Created by field coordinators or org managers.

    allocation_score: computed by AllocationService (0-100)
    reasoning: structured JSON breakdown of score components for auditability
    """

    __tablename__ = "assignments"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("volunteers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status_enum"),
        default=AssignmentStatus.pending,
        nullable=False,
        index=True,
    )
    allocation_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    # {"skill_match": 25, "availability": 20, "distance": 18, "language": 10, ...}
    reasoning: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ───────────────────────────────────────────────────────
    case: Mapped["Case"] = relationship("Case", back_populates="assignments")
    volunteer: Mapped["Volunteer"] = relationship("Volunteer", back_populates="assignments")
    assigned_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<Assignment id={self.id} case={self.case_id} volunteer={self.volunteer_id}>"
