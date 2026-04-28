"""Optional IMD warning client.

The endpoint shape varies by feed and access method, so the code uses a URL
template from env and keeps parsing deliberately defensive.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings


class IMDWarningsClient:
    def fetch_warnings(self, state: str | None, district: str | None) -> list[dict[str, Any]]:
        if not settings.IMD_WARNINGS_URL_TEMPLATE or not state or not district:
            return []

        url = settings.IMD_WARNINGS_URL_TEMPLATE.format(
            state=quote(state),
            district=quote(district),
        )
        headers = {}
        if settings.IMD_API_KEY:
            headers["Authorization"] = f"Bearer {settings.IMD_API_KEY}"

        response = httpx.get(url, headers=headers, timeout=settings.IMD_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("warnings", "data", "items", "alerts"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [payload]
        return []
