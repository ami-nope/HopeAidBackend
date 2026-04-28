"""app/workers/celery_app.py — Celery application factory and beat schedule."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "hopeaid",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.ocr_tasks",
        "app.workers.tasks.ai_tasks",
        "app.workers.tasks.report_tasks",
        "app.workers.tasks.weather_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_ack_late=True,  # Re-queue if worker crashes
    worker_prefetch_multiplier=1,  # Fair distribution
    task_routes={
        "app.workers.tasks.ocr_tasks.*": {"queue": "ocr"},
        "app.workers.tasks.ai_tasks.*": {"queue": "ai"},
        "app.workers.tasks.report_tasks.*": {"queue": "reports"},
        "app.workers.tasks.weather_tasks.*": {"queue": "ai"},
    },
    # ─── Celery Beat Schedule ──────────────────────────────────────────────
    beat_schedule={
        # Check for unassigned critical cases every 30 minutes
        "check-unassigned-critical": {
            "task": "app.workers.tasks.ai_tasks.check_unassigned_critical_cases",
            "schedule": crontab(minute="*/30"),
        },
        # Generate daily summary report at midnight UTC
        "daily-report-summary": {
            "task": "app.workers.tasks.report_tasks.generate_daily_summary",
            "schedule": crontab(hour=0, minute=0),
        },
        # Check inventory for low stock / expiry daily at 6 AM UTC
        "inventory-health-check": {
            "task": "app.workers.tasks.ai_tasks.check_inventory_health",
            "schedule": crontab(hour=6, minute=0),
        },
        "weather-intelligence-check": {
            "task": "app.workers.tasks.weather_tasks.scan_due_weather_cases",
            "schedule": crontab(minute="*/30"),
        },
    },
)
