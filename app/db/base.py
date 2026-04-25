"""
app/db/base.py — SQLAlchemy declarative base and shared column mixins.

All models import Base from here. TimestampMixin adds created_at/updated_at
to any model automatically.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.
    Provides type annotations and dialect-aware UUID primary keys.
    """

    type_annotation_map: dict[type, Any] = {}


class UUIDMixin:
    """Mixin: UUID primary key generated at the Python layer."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Mixin: created_at / updated_at timestamps, always UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
