"""app/schemas/upload.py — Upload and AI extraction schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from app.core.constants import AIInputType, FileType, ProcessingStatus, UploadSource
from app.schemas.common import HopeAidBase


class UploadOut(HopeAidBase):
    id: UUID
    organization_id: UUID
    uploaded_by_user_id: Optional[UUID]
    file_url: str
    file_name: Optional[str]
    file_type: FileType
    file_size_bytes: Optional[int]
    source: UploadSource
    related_case_id: Optional[UUID]
    extracted_text: Optional[str]
    processing_status: ProcessingStatus
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class UploadReviewRequest(HopeAidBase):
    approved: bool
    review_notes: Optional[str] = None
    # If approved and no case exists yet, caller can override structured fields
    overrides: Optional[dict[str, Any]] = None


class AIExtractionOut(HopeAidBase):
    id: UUID
    upload_id: Optional[UUID]
    organization_id: UUID
    input_type: AIInputType
    raw_input: Optional[str]
    structured_json: Optional[dict[str, Any]]
    confidence: Optional[float]
    model_used: Optional[str]
    prompt_version: Optional[str]
    reviewed_by_user_id: Optional[UUID]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    created_at: datetime


class ExtractCaseRequest(HopeAidBase):
    """Free-text case extraction request."""
    text: str = Field(..., min_length=10, max_length=10000)
    source_language: Optional[str] = None  # ISO 639-1


class TranslateRequest(HopeAidBase):
    text: str = Field(..., min_length=1, max_length=5000)
    target_language: str = Field(..., min_length=2, max_length=10)  # ISO 639-1
    source_language: Optional[str] = None
    save: bool = False  # Whether to persist translation


class TranslateResponse(HopeAidBase):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


class SummarizeCaseRequest(HopeAidBase):
    case_id: UUID
    target_language: Optional[str] = None


class ReportSummaryRequest(HopeAidBase):
    period: str = "daily"  # daily | weekly | monthly
    disaster_type: Optional[str] = None
