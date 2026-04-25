"""
app/workers/tasks/ocr_tasks.py — Celery tasks for file OCR processing. All sync.

Flow:
  1. ocr_process_upload(upload_id) — triggered after file upload
  2. Fetches file bytes from S3 URL via requests
  3. Runs Google Vision OCR (synchronous)
  4. Updates Upload.extracted_text and processing_status
  5. Chains to ai_extract_from_upload for structured extraction
"""

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.workers.tasks.ocr_tasks.ocr_process_upload",
)
def ocr_process_upload(self, upload_id: str, organization_id: str) -> dict:
    """
    Process an uploaded file with OCR.

    Args:
        upload_id: UUID string of the Upload record
        organization_id: UUID string of the organization

    Returns:
        dict with extracted_text and status
    """
    import requests

    from app.core.constants import ProcessingStatus
    from app.db.session import SessionLocal
    from app.integrations.ocr.google_vision import extract_text_from_image
    from app.models.upload import Upload

    try:
        db = SessionLocal()
        try:
            upload = db.get(Upload, upload_id)
            if not upload:
                logger.error("Upload not found", upload_id=upload_id)
                return {"status": "error", "reason": "upload_not_found"}

            # Mark as processing
            upload.processing_status = ProcessingStatus.processing
            db.commit()

            # Fetch file bytes from S3 URL using requests (sync HTTP)
            try:
                response = requests.get(upload.file_url, timeout=30)
                response.raise_for_status()
                file_bytes = response.content
            except Exception as exc:
                upload.processing_status = ProcessingStatus.failed
                upload.error_message = f"Failed to fetch file: {exc}"
                db.commit()
                return {"status": "error", "reason": str(exc)}

            # Determine MIME type from file_type
            mime_map = {"image": "image/jpeg", "pdf": "application/pdf"}
            mime_type = mime_map.get(upload.file_type.value, "image/jpeg")

            # Run OCR (synchronous)
            extracted_text = extract_text_from_image(file_bytes, mime_type)

            if extracted_text:
                upload.extracted_text = extracted_text
                upload.processing_status = ProcessingStatus.completed
                db.commit()

                # Chain to AI extraction task
                from app.workers.tasks.ai_tasks import ai_extract_from_upload
                ai_extract_from_upload.delay(upload_id, organization_id, extracted_text)

                logger.info("OCR completed, chained to AI extraction", upload_id=upload_id)
                return {"status": "completed", "chars": len(extracted_text)}
            else:
                upload.processing_status = ProcessingStatus.failed
                upload.error_message = "OCR returned no text"
                db.commit()
                return {"status": "failed", "reason": "no_text_extracted"}
        finally:
            db.close()

    except Exception as exc:
        logger.error("OCR task failed", upload_id=upload_id, error=str(exc))
        raise self.retry(exc=exc)
