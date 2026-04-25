"""app/models/upload.py — File upload and AI extraction result models."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AIInputType, FileType, ProcessingStatus, UploadSource
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass


class Upload(UUIDMixin, TimestampMixin, Base):
    """
    A file uploaded to S3-compatible storage.
    OCR and AI extraction are kicked off as Celery tasks on upload.
    """

    __tablename__ = "uploads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_type: Mapped[FileType] = mapped_column(
        SAEnum(FileType, name="file_type_enum"), nullable=False
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source: Mapped[UploadSource] = mapped_column(
        SAEnum(UploadSource, name="upload_source_enum"),
        default=UploadSource.other,
        nullable=False,
    )
    related_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, name="processing_status_enum"),
        default=ProcessingStatus.pending,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── Relationships ───────────────────────────────────────────────────────
    extraction_results: Mapped[list["AIExtractionResult"]] = relationship(
        "AIExtractionResult", back_populates="upload", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Upload id={self.id} status={self.processing_status}>"


class AIExtractionResult(UUIDMixin, Base):
    """
    Structured output from AI/LLM extraction of case data from raw text.
    Stores model used, prompt version, and confidence for reproducibility.
    """

    __tablename__ = "ai_extraction_results"

    upload_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_type: Mapped[AIInputType] = mapped_column(
        SAEnum(AIInputType, name="ai_input_type_enum"), nullable=False
    )
    raw_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # ─── Relationships ───────────────────────────────────────────────────────
    upload: Mapped[Optional["Upload"]] = relationship("Upload", back_populates="extraction_results")
