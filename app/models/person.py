"""app/models/person.py — Individual beneficiary / person model."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import Gender
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.household import Household
    from app.models.case import CasePerson


class Person(UUIDMixin, TimestampMixin, Base):
    """
    Individual beneficiary within a household.
    Special flags (pregnant, disabled, children) inform risk scoring.
    """

    __tablename__ = "persons"

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    gender: Mapped[Optional[Gender]] = mapped_column(
        SAEnum(Gender, name="gender_enum"), nullable=True
    )
    relation_to_head: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    special_needs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_children: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pregnant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_disability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medical_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    id_proof_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    household: Mapped["Household"] = relationship("Household", back_populates="persons")
    case_links: Mapped[list["CasePerson"]] = relationship(
        "CasePerson", back_populates="person"
    )

    def __repr__(self) -> str:
        return f"<Person id={self.id} name={self.name}>"
