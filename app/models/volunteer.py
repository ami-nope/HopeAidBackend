"""app/models/volunteer.py — Volunteer and VolunteerAvailability models."""

import uuid
from datetime import date, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AvailabilityStatus, DutyType
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.assignment import Assignment


class Volunteer(UUIDMixin, TimestampMixin, Base):
    """
    A volunteer registered with an organization.
    Can optionally link to a User account (user_id).
    Skills and languages stored as JSONB arrays for flexible querying.
    """

    __tablename__ = "volunteers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    current_location_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    # e.g. ["first_aid", "counseling", "logistics"]
    skills: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    # ISO 639-1 language codes: ["en", "hi", "ta"]
    languages: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    has_transport: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_medical_training: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duty_type: Mapped[DutyType] = mapped_column(
        SAEnum(DutyType, name="duty_type_enum"),
        default=DutyType.on_call,
        nullable=False,
    )
    # Scale: 1.0–10.0. Updated when assignments are completed/rated
    reliability_score: Mapped[float] = mapped_column(Numeric(4, 2), default=5.0, nullable=False)
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        SAEnum(AvailabilityStatus, name="availability_status_enum"),
        default=AvailabilityStatus.available,
        nullable=False,
        index=True,
    )
    # Denormalized counter — updated when assignments are created/completed
    active_assignment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ─── Relationships ───────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship("Organization", back_populates="volunteers")
    availability_slots: Mapped[list["VolunteerAvailability"]] = relationship(
        "VolunteerAvailability", back_populates="volunteer", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="volunteer"
    )

    def __repr__(self) -> str:
        return f"<Volunteer id={self.id} name={self.name}>"


class VolunteerAvailability(UUIDMixin, Base):
    """
    Weekly recurring availability windows for a volunteer.
    day_of_week: 0=Monday ... 6=Sunday
    valid_from/valid_until: optional date range for seasonal availability
    """

    __tablename__ = "volunteer_availability"

    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("volunteers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0=Mon, 6=Sun
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    volunteer: Mapped["Volunteer"] = relationship("Volunteer", back_populates="availability_slots")
