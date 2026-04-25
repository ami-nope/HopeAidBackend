"""
app/workers/tasks/ai_tasks.py — Celery tasks for AI extraction and alert checking. All sync.

Celery tasks are always synchronous functions (the @celery_app.task decorator
requires regular def, not async def). DB access uses the sync SessionLocal.
"""

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="app.workers.tasks.ai_tasks.ai_extract_from_upload",
)
def ai_extract_from_upload(self, upload_id: str, organization_id: str, raw_text: str) -> dict:
    """Extract structured case fields from OCR text using LLM."""
    import uuid
    from app.db.session import SessionLocal
    from app.integrations.llm.openai_client import extract_case_from_text
    from app.models.upload import AIExtractionResult
    from app.core.constants import AIInputType
    from app.core.config import settings

    try:
        structured = extract_case_from_text(raw_text)
        if not structured:
            return {"status": "skipped", "reason": "ai_not_configured_or_failed"}

        db = SessionLocal()
        try:
            result = AIExtractionResult(
                upload_id=uuid.UUID(upload_id),
                organization_id=uuid.UUID(organization_id),
                input_type=AIInputType.ocr,
                raw_input=raw_text[:5000],
                structured_json=structured,
                confidence=structured.get("confidence"),
                model_used=settings.OPENAI_MODEL,
                prompt_version="v1.2",
            )
            db.add(result)
            db.commit()
            logger.info("AI extraction result saved", upload_id=upload_id)
            return {"status": "completed", "extraction_id": str(result.id)}
        finally:
            db.close()

    except Exception as exc:
        logger.error("AI extraction task failed", upload_id=upload_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.ai_tasks.check_unassigned_critical_cases")
def check_unassigned_critical_cases() -> dict:
    """Periodic task: create alerts for critical cases with no volunteer assignments."""
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.case import Case
    from app.models.assignment import Assignment
    from app.models.alert import Alert
    from app.core.constants import CaseStatus, UrgencyLevel, AlertType, AlertStatus, RecipientType

    try:
        db = SessionLocal()
        try:
            critical_cases = db.execute(
                select(Case).where(
                    Case.urgency_level == UrgencyLevel.critical,
                    Case.status.in_([CaseStatus.new, CaseStatus.verified]),
                )
            ).scalars().all()

            alert_count = 0

            for case in critical_cases:
                has_assignment = db.execute(
                    select(Assignment).where(Assignment.case_id == case.id)
                ).scalars().first()

                if not has_assignment:
                    existing_alert = db.execute(
                        select(Alert).where(
                            Alert.case_id == case.id,
                            Alert.type == AlertType.unassigned_critical,
                            Alert.status == AlertStatus.active,
                        )
                    ).scalars().first()

                    if not existing_alert:
                        alert = Alert(
                            organization_id=case.organization_id,
                            case_id=case.id,
                            type=AlertType.unassigned_critical,
                            message=f"Critical case {case.case_number} has no volunteer assigned.",
                            recipient_type=RecipientType.org_manager,
                        )
                        db.add(alert)
                        alert_count += 1

            db.commit()
            logger.info("Critical case check completed", alerts_created=alert_count)
            return {"status": "completed", "alerts_created": alert_count}
        finally:
            db.close()

    except Exception as exc:
        logger.error("Critical case check failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="app.workers.tasks.ai_tasks.check_inventory_health")
def check_inventory_health() -> dict:
    """Daily task: flag low stock and expired inventory items, create alerts."""
    from datetime import date
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.inventory import InventoryItem
    from app.models.alert import Alert
    from app.core.constants import InventoryStatus, AlertType, RecipientType

    try:
        db = SessionLocal()
        try:
            items = db.execute(select(InventoryItem)).scalars().all()
            alerts_created = 0

            for item in items:
                # Check expiry
                if item.expiry_date and item.expiry_date <= date.today():
                    item.status = InventoryStatus.expired

                # Check low stock threshold
                if item.minimum_threshold and item.quantity <= item.minimum_threshold:
                    item.status = InventoryStatus.low_stock
                    alert = Alert(
                        organization_id=item.organization_id,
                        type=AlertType.inventory_low,
                        message=f"Inventory low: {item.item_name} ({item.quantity} {item.unit or 'units'} remaining)",
                        recipient_type=RecipientType.org_manager,
                        metadata_json={"item_id": str(item.id), "quantity": float(item.quantity)},
                    )
                    db.add(alert)
                    alerts_created += 1

                if item.quantity <= 0:
                    item.status = InventoryStatus.out_of_stock

            db.commit()
            return {"status": "completed", "alerts_created": alerts_created}
        finally:
            db.close()

    except Exception as exc:
        logger.error("Inventory health check failed", error=str(exc))
        return {"status": "error"}
