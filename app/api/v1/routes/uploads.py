"""app/api/v1/routes/uploads.py — File upload and OCR/AI processing endpoints. All sync."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.constants import UploadSource
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.upload import AIExtractionOut, UploadOut, UploadReviewRequest
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["Uploads & OCR"])


@router.post("", response_model=APIResponse[UploadOut], status_code=201)
def upload_file(
    file: UploadFile = File(...),
    source: UploadSource = Form(UploadSource.other),
    related_case_id: Optional[UUID] = Form(None),
    auto_process: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a file to storage. If auto_process=True and file is image/PDF,
    OCR processing is queued automatically via Celery.
    """
    try:
        service = UploadService(db, current_user)
        upload = service.handle_upload(
            file=file,
            source=source,
            related_case_id=related_case_id,
            auto_process=auto_process,
        )
        db.commit()
        db.refresh(upload)
        return {"success": True, "data": UploadOut.model_validate(upload)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.get("/{upload_id}", response_model=APIResponse[UploadOut])
def get_upload(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = UploadService(db, current_user)
    upload = service.get_upload(upload_id)
    if not upload:
        raise HTTPException(404, "Upload not found")
    return {"success": True, "data": UploadOut.model_validate(upload)}


@router.post("/{upload_id}/process", response_model=APIResponse[None])
def trigger_processing(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger OCR processing for an already-uploaded file."""
    try:
        service = UploadService(db, current_user)
        service.trigger_processing(upload_id)
        db.commit()
        return {"success": True, "message": "Processing task queued"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{upload_id}/review", response_model=APIResponse[AIExtractionOut])
def review_extraction(
    upload_id: UUID,
    request: UploadReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Human review of AI extraction result. Approve or reject with optional field overrides."""
    try:
        service = UploadService(db, current_user)
        extraction = service.review_extraction(
            upload_id=upload_id,
            approved=request.approved,
            review_notes=request.review_notes,
            overrides=request.overrides,
        )
        db.commit()
        db.refresh(extraction)
        return {"success": True, "data": AIExtractionOut.model_validate(extraction)}
    except ValueError as e:
        raise HTTPException(400, str(e))
