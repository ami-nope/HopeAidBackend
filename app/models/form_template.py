"""app/models/form_template.py — Admin-configurable intake form templates."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class FormTemplate(UUIDMixin, TimestampMixin, Base):
    """
    Custom intake form templates configured per organization.
    fields_json defines the form schema (field name, type, required, options).
    Version is incremented on each update to preserve history.
    """

    __tablename__ = "form_templates"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    form_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Example: [{"name": "victim_count", "type": "integer", "required": true, "label": "# Victims"}]
    fields_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<FormTemplate id={self.id} name={self.form_name} v{self.version}>"
