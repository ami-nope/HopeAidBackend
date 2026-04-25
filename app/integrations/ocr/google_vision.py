"""
app/integrations/ocr/google_vision.py — Google Cloud Vision OCR integration. All sync.

Sends image bytes to Google Vision API and returns extracted text.
Falls back gracefully if GOOGLE_APPLICATION_CREDENTIALS is not configured.
"""

from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[str]:
    """
    Run OCR on image bytes using Google Cloud Vision API (synchronous client).

    Returns extracted text string, or None if OCR fails or is not configured.
    """
    if not settings.GOOGLE_APPLICATION_CREDENTIALS:
        logger.warning("Google Vision OCR not configured — GOOGLE_APPLICATION_CREDENTIALS missing")
        return None

    if not settings.ENABLE_OCR:
        logger.info("OCR disabled via ENABLE_OCR=false")
        return None

    try:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.document_text_detection(image=image)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        full_text = response.full_text_annotation.text
        logger.info("OCR extraction completed", chars=len(full_text))
        return full_text

    except ImportError:
        logger.error("google-cloud-vision not installed")
        return None
    except Exception as exc:
        logger.error("OCR extraction failed", error=str(exc))
        return None
