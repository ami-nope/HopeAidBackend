"""app/models/report.py — Report generation job model."""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ReportFormat, ReportStatus, ReportType
from app.db.base import Base, UUIDMixin


class ReportJob(UUIDMixin, Base):
    """
    Async report generation job. Celery task generates the file and
    uploads it to S3, then updates output_url and status.
    """

    __tablename__ = "report_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_type: Mapped[ReportType] = mapped_column(
        SAEnum(ReportType, name="report_type_enum"), nullable=False
    )
    filters_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[ReportFormat] = mapped_column(
        SAEnum(ReportFormat, name="report_format_enum"),
        default=ReportFormat.csv,
        nullable=False,
    )
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status_enum"),
        default=ReportStatus.pending,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ReportJob id={self.id} type={self.report_type} status={self.status}>"
