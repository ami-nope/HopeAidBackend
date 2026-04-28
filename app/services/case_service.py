"""
app/services/case_service.py — Case CRUD and workflow service.

Handles:
- Case creation with auto case_number generation
- Status transitions (verify, assign, close, reject)
- Risk score computation
- Duplicate checking

Synchronous — no async, no await.
"""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import CaseStatus, GeocodeStatus, UserRole, VerificationStatus
from app.core.logging import get_logger
from app.models.case import Case
from app.models.person import Person
from app.models.user import User
from app.schemas.case import CaseCreate, CaseRejectRequest, CaseUpdate, DuplicateCheckResult
from app.services.audit_service import log_action
from app.utils.duplicate_detector import compute_duplicate_confidence, is_likely_duplicate
from app.utils.risk_scorer import compute_risk_score

logger = get_logger(__name__)


def _generate_case_number(db: Session, org_slug: str) -> str:
    """Generate a sequential case number: ORGSLUG-YYYY-NNNNN."""
    year = datetime.now(UTC).year
    prefix = f"{org_slug.upper()[:8]}-{year}-"
    count = db.execute(
        select(func.count(Case.id)).where(Case.case_number.like(f"{prefix}%"))
    ).scalar() or 0
    return f"{prefix}{count + 1:05d}"


class CaseService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.org_id = current_user.organization_id
        self.is_global_super_admin = (
            current_user.role == UserRole.super_admin and current_user.organization_id is None
        )

    def create_case(self, data: CaseCreate) -> Case:
        """Create a new case with computed risk score and auto case number."""
        from app.models.organization import Organization
        org_id = self.org_id
        if self.is_global_super_admin and data.organization_id:
            org_id = data.organization_id
        if org_id is None:
            raise ValueError("organization_id is required for global super admin")

        org = self.db.get(Organization, org_id)
        if not org:
            raise ValueError("Organization not found")

        case_number = _generate_case_number(self.db, org.slug)

        # Compute initial risk score using the rule-based scorer
        risk = compute_risk_score(
            urgency_level=data.urgency_level,
            disaster_type=data.disaster_type,
            number_of_people_affected=data.number_of_people_affected,
            created_at=datetime.now(UTC),
            resource_needed_count=len(data.resource_needed) if data.resource_needed else 0,
        )

        case = Case(
            organization_id=org_id,
            household_id=data.household_id,
            reporter_user_id=self.current_user.id,
            ai_extraction_id=data.ai_extraction_id,
            case_number=case_number,
            title=data.title,
            description=data.description,
            category=data.category,
            subcategory=data.subcategory,
            urgency_level=data.urgency_level,
            risk_score=risk,
            disaster_type=data.disaster_type,
            location_name=data.location_name,
            latitude=data.latitude,
            longitude=data.longitude,
            situation_type=data.situation_type,
            special_requirements=data.special_requirements,
            resource_needed=[r.model_dump() for r in data.resource_needed] if data.resource_needed else None,
            number_of_people_affected=data.number_of_people_affected,
            source_type=data.source_type,
            geocode_status=(
                GeocodeStatus.resolved
                if data.latitude is not None and data.longitude is not None
                else GeocodeStatus.pending
                if data.location_name
                else GeocodeStatus.not_requested
            ),
            geocode_provider="manual" if data.latitude is not None and data.longitude is not None else None,
            confidence_score=data.confidence_score,
            status=CaseStatus.new,
            next_weather_check_at=datetime.now(UTC)
            if data.location_name or (data.latitude is not None and data.longitude is not None)
            else None,
        )
        self.db.add(case)
        self.db.flush()   # Flush to get the generated ID

        log_action(
            self.db,
            organization_id=org_id,
            actor_user_id=self.current_user.id,
            action_type="CASE_CREATED",
            entity_type="case",
            entity_id=case.id,
            after_json={"case_number": case_number, "title": data.title},
        )
        logger.info("Case created", case_id=str(case.id), case_number=case_number)
        return case

    def get_case(self, case_id: uuid.UUID) -> Optional[Case]:
        """Fetch a single case by ID, scoped to organization."""
        query = select(Case).where(Case.id == case_id)
        if not self.is_global_super_admin:
            query = query.where(Case.organization_id == self.org_id)
        return self.db.execute(query).scalars().first()

    def list_cases(
        self,
        status: Optional[CaseStatus] = None,
        urgency: Optional[str] = None,
        q: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Case], int]:
        """List cases with optional filters, returns (rows, total_count)."""
        query = select(Case)
        if not self.is_global_super_admin:
            query = query.where(Case.organization_id == self.org_id)
        if status:
            query = query.where(Case.status == status)
        if urgency:
            query = query.where(Case.urgency_level == urgency)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(or_(
                Case.case_number.ilike(pattern),
                Case.title.ilike(pattern),
                Case.description.ilike(pattern),
                Case.location_name.ilike(pattern),
            ))

        total = self.db.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar()

        cases = self.db.execute(
            query.order_by(Case.created_at.desc()).offset(offset).limit(limit)
        ).scalars().all()
        return cases, total

    def update_case(self, case_id: uuid.UUID, data: CaseUpdate) -> Case:
        """Update editable fields of a case."""
        case = self.get_case(case_id)
        if not case:
            raise ValueError("Case not found")

        before = {"title": case.title, "status": case.status.value}
        for field, value in data.model_dump(exclude_none=True).items():
            if field == "resource_needed" and value:
                setattr(case, field, [r if isinstance(r, dict) else r.model_dump() for r in value])
            else:
                setattr(case, field, value)

        if {"location_name", "latitude", "longitude"} & set(data.model_dump(exclude_none=True).keys()):
            if case.latitude is not None and case.longitude is not None:
                case.geocode_status = GeocodeStatus.resolved
                case.geocode_provider = case.geocode_provider or "manual"
                case.next_weather_check_at = datetime.now(UTC)
            elif case.location_name:
                case.geocode_status = GeocodeStatus.pending
                case.next_weather_check_at = datetime.now(UTC)
            else:
                case.geocode_status = GeocodeStatus.not_requested
                case.next_weather_check_at = None

        # Recompute risk score if relevant fields changed
        if data.urgency_level or data.number_of_people_affected or data.disaster_type:
            case.risk_score = compute_risk_score(
                urgency_level=case.urgency_level,
                disaster_type=case.disaster_type,
                number_of_people_affected=case.number_of_people_affected,
                created_at=case.created_at,
                resource_needed_count=len(case.resource_needed) if case.resource_needed else 0,
            )

        log_action(
            self.db, self.org_id, self.current_user.id,
            "CASE_UPDATED", "case", case.id,
            before_json=before, after_json={"title": case.title},
        )
        return case

    def approve_case(self, case_id: uuid.UUID) -> Case:
        """Verify a case — transitions: new → verified."""
        case = self.get_case(case_id)
        if not case:
            raise ValueError("Case not found")
        if case.status != CaseStatus.new:
            raise ValueError(f"Cannot approve case in status '{case.status.value}'")

        case.status = CaseStatus.verified
        case.verification_status = VerificationStatus.verified

        log_action(
            self.db, self.org_id, self.current_user.id,
            "CASE_APPROVED", "case", case.id,
            before_json={"status": "new"},
            after_json={"status": "verified"},
        )
        return case

    def reject_case(self, case_id: uuid.UUID, request: CaseRejectRequest) -> Case:
        """Reject a case with a reason."""
        case = self.get_case(case_id)
        if not case:
            raise ValueError("Case not found")
        if case.status in {CaseStatus.resolved, CaseStatus.closed}:
            raise ValueError("Cannot reject a resolved/closed case")

        before_status = case.status.value
        case.status = CaseStatus.rejected
        case.verification_status = VerificationStatus.disputed
        rejection_note = f"[REJECTED]: {request.reason}"
        case.special_requirements = (
            f"{case.special_requirements}\n{rejection_note}"
            if case.special_requirements else rejection_note
        )

        log_action(
            self.db, self.org_id, self.current_user.id,
            "CASE_REJECTED", "case", case.id,
            before_json={"status": before_status},
            after_json={"status": "rejected", "reason": request.reason},
        )
        return case

    def close_case(self, case_id: uuid.UUID) -> Case:
        """Close a case that is assigned, in_progress, or resolved."""
        case = self.get_case(case_id)
        if not case:
            raise ValueError("Case not found")
        if case.status not in {CaseStatus.in_progress, CaseStatus.resolved, CaseStatus.assigned}:
            raise ValueError("Case must be in_progress, assigned, or resolved to close")

        case.status = CaseStatus.closed
        case.closed_at = datetime.now(UTC)

        log_action(
            self.db, self.org_id, self.current_user.id,
            "CASE_CLOSED", "case", case.id,
            after_json={"status": "closed"},
        )
        return case

    def recalculate_risk(self, case_id: uuid.UUID) -> Case:
        """Recompute risk score using current data including linked persons."""
        case = self.get_case(case_id)
        if not case:
            raise ValueError("Case not found")

        from app.models.case import CasePerson
        case_persons = self.db.execute(
            select(CasePerson).where(CasePerson.case_id == case.id)
        ).scalars().all()

        has_vuln = False
        vuln_count = 0
        for cp in case_persons:
            person = self.db.get(Person, cp.person_id)
            if person and (person.has_disability or person.is_pregnant or person.has_children):
                has_vuln = True
                vuln_count += 1

        case.risk_score = compute_risk_score(
            urgency_level=case.urgency_level,
            disaster_type=case.disaster_type,
            number_of_people_affected=case.number_of_people_affected,
            created_at=case.created_at,
            has_vulnerable_persons=has_vuln,
            vulnerable_person_count=vuln_count,
            resource_needed_count=len(case.resource_needed) if case.resource_needed else 0,
        )
        return case

    def check_duplicate(self, case_id: uuid.UUID) -> DuplicateCheckResult:
        """Compare this case against recent cases for potential duplicates."""
        case = self.get_case(case_id)
        if not case:
            raise ValueError("Case not found")

        existing_cases = self.db.execute(
            select(Case).where(
                Case.organization_id == self.org_id,
                Case.id != case_id,
                Case.status != CaseStatus.rejected,
            ).order_by(Case.created_at.desc()).limit(500)
        ).scalars().all()

        new_dict = {
            "contact_phone": None,
            "household_name": case.title,
            "location_name": case.location_name,
            "latitude": float(case.latitude) if case.latitude else None,
            "longitude": float(case.longitude) if case.longitude else None,
            "title": case.title,
        }

        if case.household_id:
            from app.models.household import Household
            hh = self.db.get(Household, case.household_id)
            if hh:
                new_dict["contact_phone"] = hh.contact_phone
                new_dict["household_name"] = hh.household_name

        matched = []
        for existing in existing_cases:
            ex_dict = {
                "title": existing.title,
                "location_name": existing.location_name,
                "latitude": float(existing.latitude) if existing.latitude else None,
                "longitude": float(existing.longitude) if existing.longitude else None,
            }
            confidence = compute_duplicate_confidence(new_dict, ex_dict)
            if confidence >= 50:
                matched.append({
                    "case_id": str(existing.id),
                    "case_number": existing.case_number,
                    "title": existing.title,
                    "confidence": confidence,
                })

        matched.sort(key=lambda x: x["confidence"], reverse=True)
        top_matches = matched[:5]
        max_conf = top_matches[0]["confidence"] if top_matches else 0.0

        return DuplicateCheckResult(
            is_duplicate=is_likely_duplicate(max_conf),
            confidence=max_conf,
            matched_cases=top_matches,
            explanation=f"Found {len(top_matches)} potential duplicate(s) with confidence up to {max_conf:.1f}%.",
        )
