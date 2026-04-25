"""
app/integrations/translation/google_translate.py — Google Cloud Translation API. All sync.

Translates text to a target language using the sync google-cloud-translate client.
Returns the original text if translation is not configured.
"""

from typing import Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def translate_text(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Translate text to target_language using Google Cloud Translation API.

    Args:
        text: Source text
        target_language: ISO 639-1 target language code (e.g. "hi", "ta", "fr")
        source_language: ISO 639-1 source language (optional, auto-detected if None)

    Returns:
        Tuple of (translated_text, detected_source_language)
    """
    if not settings.GOOGLE_APPLICATION_CREDENTIALS or not settings.ENABLE_TRANSLATION:
        logger.warning("Translation not configured or disabled — returning original text")
        return text, source_language or "en"

    try:
        from google.cloud import translate_v2 as translate

        client = translate.Client()
        result = client.translate(
            text,
            target_language=target_language,
            source_language=source_language,
        )

        translated = result["translatedText"]
        detected_source = result.get("detectedSourceLanguage", source_language or "en")
        logger.info(
            "Translation completed",
            source=detected_source,
            target=target_language,
            input_chars=len(text),
        )
        return translated, detected_source

    except ImportError:
        logger.error("google-cloud-translate not installed")
        return text, source_language or "en"
    except Exception as exc:
        logger.error("Translation failed", error=str(exc))
        return text, source_language or "en"
