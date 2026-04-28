"""Periodic weather intelligence tasks."""

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.weather_intelligence_service import WeatherIntelligenceService
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.weather_tasks.scan_due_weather_cases")
def scan_due_weather_cases() -> dict:
    try:
        db = SessionLocal()
        try:
            service = WeatherIntelligenceService(db)
            result = service.scan_due_cases()
            db.commit()
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.error("Weather intelligence batch failed", error=str(exc))
        return {"status": "error", "error": str(exc)}
