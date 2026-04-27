"""Phone normalization helpers."""

from __future__ import annotations

import re
from typing import Optional


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize arbitrary phone input into a canonical E.164-like format: +<digits>.
    Returns None for empty/invalid input.
    """
    if phone is None:
        return None

    raw = phone.strip()
    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    return f"+{digits}"

