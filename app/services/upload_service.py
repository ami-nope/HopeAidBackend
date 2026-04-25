"""
app/services/upload_service.py — File upload handling and OCR trigger service.

Synchronous — no async, no await.
Note: file.read() from UploadFile is made synchronous via FastAPI's sync route support.
"""

import uuid
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import FileType, ProcessingStatus, UploadSource
from app.core.logging import get_logger
from app.integrations.storage.s3_client import upload_file
from app.models.upload import AIExtractionResult, Upload
from app.models.user import User

logger = get_logger(__name__)

# Maps MIME content type → our internal FileType enum
MIME_TO_FILE_TYPE = {
    "image/jpeg": FileType.image,
    "image/png": FileType.image,
    "image/webp": FileType.image,
    "image/gif": FileType.image,
    "application/pdf": FileType.pdf,
    "audio/wav": FileType.audio,
    "audio/mpeg": FileType.audio,
    "audio/mp4": FileType.audio,
}


class UploadService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.org_id = current_user.organization_id

    def handle_upload(
        self,
        file: UploadFile,
        source: UploadSource = UploadSource.other,
        related_case_id: Optional[uuid.UUID] = None,
        auto_process: bool = True,
    ) -> Upload:
        """
        Read the uploaded file, save to S3, create Upload DB record,
        and optionally queue an OCR Celery task.
        """
        # Read file bytes synchronously
        file_bytes = file.file.read()
        content_type = file.content_type or "application/octet-stream"

        # Upload to S3-compatible storage
        file_url = upload_file(
            file_bytes=file_bytes,
            original_filename=file.filename or "upload",
            content_type=content_type,
            organization_id=str(self.org_id),
        )

        file_type = MIME_TO_FILE_TYPE.get(content_type, FileType.document)
        upload = Upload(
            organization_id=self.org_id,
            uploaded_by_user_id=self.current_user.id,
            file_url=file_url,
            file_name=file.filename,
            file_type=file_type,
            file_size_bytes=len(file_bytes),
            source=source,
            related_case_id=related_case_id,
            processing_status=ProcessingStatus.pending,
        )
        self.db.add(upload)
        self.db.flush()

        # Queue OCR Celery task for images and PDFs
        if auto_process and file_type in {FileType.image, FileType.pdf}:
            from app.workers.tasks.ocr_tasks import ocr_process_upload
            ocr_process_upload.delay(str(upload.id), str(self.org_id))
            logger.info("OCR task queued", upload_id=str(upload.id))

        return upload

    def get_upload(self, upload_id: uuid.UUID) -> Optional[Upload]:
        """Fetch one upload record scoped to this organization."""
        return self.db.execute(
            select(Upload).where(
                Upload.id == upload_id,
                Upload.organization_id == self.org_id,
            )
        ).scalars().first()

    def trigger_processing(self, upload_id: uuid.UUID) -> Upload:
        """Manually re-trigger OCR for an existing upload."""
        upload = self.get_upload(upload_id)
        if not upload:
            raise ValueError("Upload not found")
        if upload.processing_status == ProcessingStatus.processing:
            raise ValueError("Upload is already being processed")

        upload.processing_status = ProcessingStatus.pending
        from app.workers.tasks.ocr_tasks import ocr_process_upload
        ocr_process_upload.delay(str(upload.id), str(self.org_id))
        return upload

    def review_extraction(
        self,
        upload_id: uuid.UUID,
        approved: bool,
        review_notes: Optional[str] = None,
        overrides: Optional[dict] = None,
    ) -> AIExtractionResult:
        """Mark an AI extraction as human-reviewed."""
        from datetime import UTC, datetime

        upload = self.get_upload(upload_id)
        if not upload:
            raise ValueError("Upload not found")

        extraction = self.db.execute(
            select(AIExtractionResult).where(AIExtractionResult.upload_id == upload_id)
        ).scalars().first()
        if not extraction:
            raise ValueError("No extraction result found for this upload")

        extraction.reviewed_by_user_id = self.current_user.id
        extraction.reviewed_at = datetime.now(UTC)
        extraction.review_notes = review_notes

        if overrides and extraction.structured_json:
            extraction.structured_json.update(overrides)

        return extraction
