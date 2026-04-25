"""
app/integrations/storage/s3_client.py — S3-compatible file storage integration. All sync.

Supports AWS S3, Supabase Storage, MinIO, and Cloudflare R2 via the boto3 interface.
Set S3_ENDPOINT_URL for non-AWS providers.
"""

import mimetypes
import uuid

from app.core.config import settings
from app.core.constants import ALLOWED_UPLOAD_TYPES, MAX_FILE_SIZE_BYTES
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_s3_client():
    """Create a boto3 S3 client configured from settings."""
    import boto3

    kwargs = {
        "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
        "region_name": settings.S3_REGION,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

    return boto3.client("s3", **kwargs)


def _build_public_url(key: str) -> str:
    """Build the public URL for an uploaded file."""
    if settings.S3_PUBLIC_BASE_URL:
        return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    if settings.S3_ENDPOINT_URL:
        return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}/{key}"
    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com/{key}"


def upload_file(
    file_bytes: bytes,
    original_filename: str,
    content_type: str,
    organization_id: str,
    prefix: str = "uploads",
) -> str:
    """
    Upload file bytes to S3 and return the public URL.

    Args:
        file_bytes: Raw file content
        original_filename: Original file name (used for extension)
        content_type: MIME type (e.g. "image/jpeg")
        organization_id: Scoped path prefix for org separation
        prefix: Sub-folder (uploads, proofs, reports, etc.)

    Returns:
        str: Public URL of the uploaded file

    Raises:
        ValueError: If file type or size is not allowed
        RuntimeError: If S3 upload fails
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size exceeds limit of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB")

    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise ValueError(f"File type '{content_type}' is not allowed")

    ext = mimetypes.guess_extension(content_type) or ".bin"
    if ext == ".jpe":
        ext = ".jpg"
    file_key = f"{prefix}/{organization_id}/{uuid.uuid4()}{ext}"

    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=file_key,
            Body=file_bytes,
            ContentType=content_type,
        )

        url = _build_public_url(file_key)
        logger.info("File uploaded to S3", key=file_key, size_bytes=len(file_bytes))
        return url

    except Exception as exc:
        logger.error("S3 upload failed", key=file_key, error=str(exc))
        raise RuntimeError(f"File upload failed: {exc}") from exc


def delete_file(file_url: str) -> bool:
    """
    Delete a file from S3 given its public URL.
    Extracts the key from the URL and calls DeleteObject.
    Returns True on success, False on failure.
    """
    try:
        base = settings.S3_PUBLIC_BASE_URL or f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com"
        key = file_url.replace(base.rstrip("/") + "/", "")

        client = _get_s3_client()
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        logger.info("File deleted from S3", key=key)
        return True

    except Exception as exc:
        logger.error("S3 delete failed", error=str(exc))
        return False
