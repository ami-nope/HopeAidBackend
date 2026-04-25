"""app/models/case.py — Case (central entity) and CasePerson association models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    CaseCategory,
    CaseStatus,
    DisasterType,
    SourceType,
    UrgencyLevel,
    VerificationStatus,
)
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.household import Household
    from app.models.user import User
    from app.models.assignment import Assignment
    from app.models.person import Person


class Case(UUIDMixin, TimestampMixin, Base):
    """
    Central entity — represents one aid case / need report.

    Status flow: new → verified → assigned → in_progress → resolved → closed
    Can also be rejected at any point before resolved.
    """

    __tablename__ = "cases"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reporter_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_extraction_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Auto-generated: ORG_SLUG-YYYY-NNNNN
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[CaseCategory] = mapped_column(
        SAEnum(CaseCategory, name="case_category_enum"), nullable=False
    )
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    urgency_level: Mapped[UrgencyLevel] = mapped_column(
        SAEnum(UrgencyLevel, name="urgency_level_enum"),
        default=UrgencyLevel.medium,
        nullable=False,
    )
    risk_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    disaster_type: Mapped[Optional[DisasterType]] = mapped_column(
        SAEnum(DisasterType, name="disaster_type_enum"), nullable=True
    )
    location_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    situation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    special_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # e.g. [{"item": "food", "quantity": 5, "unit": "kg"}]
    resource_needed: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    number_of_people_affected: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status_enum"),
        default=CaseStatus.new,
        nullable=False,
        index=True,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status_enum"),
        default=VerificationStatus.pending,
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type_enum"),
        default=SourceType.manual,
        nullable=False,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship("Organization", back_populates="cases")
    household: Mapped[Optional["Household"]] = relationship("Household", back_populates="cases")
    reporter: Mapped[Optional["User"]] = relationship("User")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="case", cascade="all, delete-orphan"
    )
    case_persons: Mapped[list["CasePerson"]] = relationship(
        "CasePerson", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Case id={self.id} number={self.case_number} status={self.status}>"


class CasePerson(UUIDMixin, Base):
    """Association between a case and one or more persons/beneficiaries."""

    __tablename__ = "case_persons"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_in_case: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vulnerability_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    case: Mapped["Case"] = relationship("Case", back_populates="case_persons")
    person: Mapped["Person"] = relationship("Person", back_populates="case_links")
