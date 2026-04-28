"""Open-Meteo geocoding client used as the default free fallback."""

from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import settings


class OpenMeteoGeocodingClient:
    def geocode(self, place_name: str) -> Optional[dict]:
        if not place_name.strip():
            return None

        response = httpx.get(
            settings.OPEN_METEO_GEOCODING_URL,
            params={
                "name": place_name.strip(),
                "count": 1,
                "language": settings.GEOCODING_LANGUAGE,
                "countryCode": settings.GEOCODING_COUNTRY_CODE,
                "format": "json",
            },
            timeout=settings.GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return None

        top = results[0]
        confidence = 70.0
        if (top.get("country_code") or "").upper() == settings.GEOCODING_COUNTRY_CODE.upper():
            confidence += 10.0
        if top.get("admin1") and top.get("admin2"):
            confidence += 10.0

        return {
            "latitude": top.get("latitude"),
            "longitude": top.get("longitude"),
            "district": top.get("admin2"),
            "state": top.get("admin1"),
            "provider": "open_meteo",
            "confidence": min(confidence, 95.0),
            "raw": top,
        }
