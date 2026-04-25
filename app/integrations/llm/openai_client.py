"""
app/integrations/llm/openai_client.py — OpenAI structured extraction and generation. All sync.

Uses the synchronous OpenAI client (openai.OpenAI, not AsyncOpenAI).
AI is optional — all functions return None if the API key is not set.
"""

import json
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CASE_EXTRACTION_PROMPT_VERSION = "v1.2"

CASE_EXTRACTION_SYSTEM_PROMPT = """
You are a humanitarian aid case intake assistant. Extract structured information from the provided text.
Return ONLY valid JSON matching this schema (omit fields you cannot confidently extract):
{
  "title": "brief descriptive title",
  "description": "full situation description",
  "category": "food|shelter|medical|clothing|water|logistics|other",
  "subcategory": "string or null",
  "urgency_level": "critical|high|medium|low",
  "disaster_type": "flood|earthquake|cyclone|drought|conflict|pandemic|fire|other|null",
  "location_name": "string or null",
  "situation_type": "string or null",
  "special_requirements": "string or null",
  "number_of_people_affected": integer or 1,
  "resource_needed": [{"item": "string", "quantity": number_or_null, "unit": "string_or_null"}],
  "contact_phone": "string or null",
  "household_name": "string or null",
  "persons": [{"name": "string", "age": int_or_null, "relation": "string_or_null", "has_disability": bool, "is_pregnant": bool}],
  "confidence": 0-100
}
Be conservative with confidence — only go above 80 if the text is clear and complete.
""".strip()


def extract_case_from_text(text: str) -> Optional[dict[str, Any]]:
    """
    Send raw text (OCR output or user input) to OpenAI and extract structured case data.
    Returns parsed dict or None on failure.
    """
    if not settings.OPENAI_API_KEY or not settings.ENABLE_AI_FEATURES:
        logger.warning("OpenAI not configured or AI features disabled")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CASE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract case information from this text:\n\n{text}"},
            ],
        )

        raw_json = response.choices[0].message.content
        result = json.loads(raw_json)
        logger.info(
            "Case extracted from text",
            confidence=result.get("confidence"),
            model=settings.OPENAI_MODEL,
            prompt_version=CASE_EXTRACTION_PROMPT_VERSION,
        )
        return result

    except Exception as exc:
        logger.error("OpenAI case extraction failed", error=str(exc))
        return None


def generate_allocation_explanation(
    case_summary: dict[str, Any],
    volunteer_profile: dict[str, Any],
    score_breakdown: dict[str, Any],
) -> str:
    """
    Generate a human-readable explanation for why a volunteer was recommended.
    Always falls back to a rule-based template if AI is unavailable.
    """
    fallback = (
        f"Volunteer {volunteer_profile.get('name', 'Unknown')} was recommended for this case "
        f"with an allocation score of {score_breakdown.get('total', 0):.1f}/100. "
        f"Skill match: {score_breakdown.get('skill_match', 0):.0f}/30, "
        f"Availability: {score_breakdown.get('availability', 0):.0f}/20, "
        f"Distance: {score_breakdown.get('distance', 0):.0f}/20, "
        f"Language match: {score_breakdown.get('language_match', 0):.0f}/10."
    )

    if not settings.OPENAI_API_KEY or not settings.ENABLE_AI_FEATURES:
        return fallback

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        system = (
            "You are a humanitarian operations coordinator. Write a clear, concise, 2-3 sentence "
            "explanation of why this volunteer is recommended for this aid case. "
            "Be specific about the matching factors. Do not fabricate details not in the input."
        )
        user = (
            f"Case: {json.dumps(case_summary)}\n"
            f"Volunteer: {json.dumps(volunteer_profile)}\n"
            f"Score breakdown: {json.dumps(score_breakdown)}"
        )

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            max_tokens=200,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:
        logger.warning("AI explanation generation failed, using fallback", error=str(exc))
        return fallback


def summarize_case(case_data: dict[str, Any], target_language: Optional[str] = None) -> Optional[str]:
    """Generate a plain-language summary of a case for volunteers or beneficiaries."""
    if not settings.OPENAI_API_KEY or not settings.ENABLE_AI_FEATURES:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        lang_instruction = f"Respond in {target_language}." if target_language else "Respond in English."
        system = (
            f"You are a humanitarian aid coordinator. Summarize this case for a volunteer. "
            f"Be factual, concise (3-4 sentences), and actionable. {lang_instruction}"
        )

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.3,
            max_tokens=300,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Case data: {json.dumps(case_data)}"},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:
        logger.error("Case summarization failed", error=str(exc))
        return None


def generate_report_narrative(stats: dict[str, Any], period: str = "daily") -> Optional[str]:
    """Generate a narrative situation report from aggregate statistics."""
    if not settings.OPENAI_API_KEY or not settings.ENABLE_AI_FEATURES:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        system = (
            f"You are a humanitarian operations analyst. Write a {period} situation report "
            f"based on these statistics. Use clear, professional language. 3-5 paragraphs. "
            f"Highlight critical items and trends."
        )

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.4,
            max_tokens=600,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Statistics: {json.dumps(stats)}"},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:
        logger.error("Report narrative generation failed", error=str(exc))
        return None
