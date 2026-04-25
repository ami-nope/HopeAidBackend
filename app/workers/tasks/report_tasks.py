"""app/workers/tasks/report_tasks.py — Celery tasks for report generation. All sync."""

import csv
import io
from datetime import datetime

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.workers.tasks.report_tasks.generate_report_job",
)
def generate_report_job(self, report_job_id: str) -> dict:
    """Generate a report CSV and upload to S3, update ReportJob record."""
    import uuid
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.report import ReportJob
    from app.models.case import Case
    from app.core.constants import ReportStatus, ReportType
    from app.integrations.storage.s3_client import upload_file

    try:
        db = SessionLocal()
        try:
            job = db.get(ReportJob, uuid.UUID(report_job_id))
            if not job:
                return {"status": "error", "reason": "job_not_found"}

            job.status = ReportStatus.processing
            db.commit()

            try:
                output_bytes = b""
                content_type = "text/csv"

                if job.report_type == ReportType.cases:
                    cases = db.execute(
                        select(Case).where(Case.organization_id == job.organization_id)
                    ).scalars().all()

                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    writer.writerow([
                        "case_number", "title", "category", "urgency_level",
                        "status", "risk_score", "number_of_people_affected",
                        "location_name", "created_at",
                    ])
                    for c in cases:
                        writer.writerow([
                            c.case_number, c.title, c.category.value,
                            c.urgency_level.value, c.status.value,
                            str(c.risk_score or ""), c.number_of_people_affected,
                            c.location_name or "", c.created_at.isoformat(),
                        ])
                    output_bytes = buf.getvalue().encode("utf-8")

                # Upload to S3
                url = upload_file(
                    output_bytes,
                    f"report_{report_job_id}.csv",
                    content_type,
                    str(job.organization_id),
                    prefix="reports",
                )

                job.output_url = url
                job.status = ReportStatus.completed
                job.completed_at = datetime.utcnow()
                db.commit()
                return {"status": "completed", "output_url": url}

            except Exception as exc:
                job.status = ReportStatus.failed
                job.error_message = str(exc)
                db.commit()
                return {"status": "error", "error": str(exc)}
        finally:
            db.close()

    except Exception as exc:
        logger.error("Report generation failed", report_job_id=report_job_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.report_tasks.generate_daily_summary")
def generate_daily_summary() -> dict:
    """Beat task: generate daily summary narrative for all active organizations."""
    from sqlalchemy import func, select
    from app.db.session import SessionLocal
    from app.models.organization import Organization
    from app.models.case import Case
    from app.integrations.llm.openai_client import generate_report_narrative
    from app.core.constants import OrgStatus

    try:
        db = SessionLocal()
        try:
            orgs = db.execute(
                select(Organization).where(Organization.status == OrgStatus.active)
            ).scalars().all()

            count = 0
            for org in orgs:
                case_count = db.execute(
                    select(func.count(Case.id)).where(Case.organization_id == org.id)
                ).scalar()

                stats = {
                    "organization": org.name,
                    "total_cases": case_count,
                    "date": datetime.utcnow().date().isoformat(),
                }
                narrative = generate_report_narrative(stats, period="daily")
                if narrative:
                    logger.info("Daily narrative generated", org_id=str(org.id))
                count += 1

            return {"status": "completed", "orgs_processed": count}
        finally:
            db.close()

    except Exception as exc:
        logger.error("Daily summary failed", error=str(exc))
        return {"status": "error"}
