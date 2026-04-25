"""app/models/organization.py — Organization (tenant) model."""

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import OrgStatus
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.case import Case
    from app.models.household import Household
    from app.models.volunteer import Volunteer


class Organization(UUIDMixin, TimestampMixin, Base):
    """
    Top-level tenant entity. Every data record belongs to an organization.
    The slug is used for human-readable identification (URL-safe).
    """

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[OrgStatus] = mapped_column(
        SAEnum(OrgStatus, name="org_status_enum"),
        default=OrgStatus.pending,
        nullable=False,
    )
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="organization")
    households: Mapped[list["Household"]] = relationship("Household", back_populates="organization")
    volunteers: Mapped[list["Volunteer"]] = relationship("Volunteer", back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug}>"
