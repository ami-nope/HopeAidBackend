"""app/models/household.py — Household / family group model."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.person import Person
    from app.models.case import Case


class Household(UUIDMixin, TimestampMixin, Base):
    """
    A household/family group — the primary beneficiary unit.
    Cases can reference a household. Multiple persons belong to one household.
    """

    __tablename__ = "households"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    # Structured flags: {"has_elderly": true, "has_infant": true, ...}
    vulnerability_flags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ─── Relationships ───────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="households"
    )
    persons: Mapped[list["Person"]] = relationship(
        "Person", back_populates="household", cascade="all, delete-orphan"
    )
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="household")

    def __repr__(self) -> str:
        return f"<Household id={self.id} name={self.household_name}>"
