"""Gemini weather alert generation.

Gemini is only used for the final decision object and human-facing alert text.
If Gemini is unavailable, callers should fall back to deterministic templates.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

WEATHER_ALERT_PROMPT_VERSION = "v1.0"


def generate_weather_alert_decision(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not settings.GEMINI_API_KEY or not settings.ENABLE_AI_FEATURES:
        return None

    prompt = (
        "You are an operations risk analyst for a disaster response platform.\n"
        "Decide whether incoming weather conditions create danger for the affected community "
        "or for volunteers trying to respond.\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "danger_for_community": true,\n'
        '  "can_be_solved": true,\n'
        '  "danger_on_volunteers": true,\n'
        '  "heading": "short alert title or null",\n'
        '  "description": "one line alert description or null",\n'
        '  "solution": "short mitigation guidance or null",\n'
        '  "full_text": "expanded explanation or null"\n'
        "}\n"
        "Rules:\n"
        "- If danger_for_community or danger_on_volunteers is true, heading and description must be non-null.\n"
        "- If both are false, heading and description must be null.\n"
        "- If can_be_solved is true, solution must be non-null.\n"
        "- Keep heading under 80 characters.\n"
        "- Keep description to one line.\n"
        "- Do not mention raw JSON or model uncertainty.\n"
    )

    try:
        response = httpx.post(
            f"{settings.GEMINI_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent",
            params={"key": settings.GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"{prompt}\n\nWeather intelligence payload:\n{json.dumps(payload)}",
                            }
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                },
            },
            timeout=20,
        )
        response.raise_for_status()
        body = response.json()
        text = (
            body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
        if not text:
            return None
        parsed = json.loads(text)
        parsed["model_used"] = settings.GEMINI_MODEL
        parsed["prompt_version"] = WEATHER_ALERT_PROMPT_VERSION
        return parsed
    except Exception as exc:
        logger.warning("Gemini weather alert generation failed", error=str(exc))
        return None
