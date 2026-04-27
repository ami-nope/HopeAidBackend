"""Helpers for distinguishing real contact data from storage-only placeholders."""

from typing import Optional


PHONE_PLACEHOLDER_DOMAIN = "phone.hopeaid.local"


def is_phone_placeholder_email(email: Optional[str]) -> bool:
    if not email:
        return False

    normalized = email.strip().lower()
    return normalized.startswith("phone_") and normalized.endswith(
        f"@{PHONE_PLACEHOLDER_DOMAIN}"
    )


def sanitize_placeholder_email(email: Optional[str]) -> Optional[str]:
    return None if is_phone_placeholder_email(email) else email
