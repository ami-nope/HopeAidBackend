"""
app/services/allocation_service.py — Volunteer allocation scoring and recommendation.

Allocation score formula (out of 100):
  Skill match    30pts — % of required skills the volunteer has
  Availability   20pts — current availability status
  Distance       20pts — closer = higher score (Haversine formula)
  Language match 10pts — any language listed
  Transport      10pts — has own vehicle
  Reliability     5pts — reliability_score / 10 * 5
  Workload        5pts — penalty for too many active assignments

Synchronous — no async, no await.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.case import Case
from app.models.volunteer import Volunteer
from app.models.user import User
from app.schemas.report import AllocationRecommendation, AllocationRecommendResponse
from app.utils.duplicate_detector import haversine_distance_km

logger = get_logger(__name__)


def compute_allocation_score(
    volunteer: Volunteer,
    case: Case,
    required_skills: list[str] = None,
) -> dict[str, Any]:
    """
    Compute all score components for one volunteer against one case.
    Returns a dict with individual scores and the total (0-100).
    """
    scores = {}

    # ── Skill Match (30pts) ───────────────────────────────────────────────────
    if required_skills and volunteer.skills:
        vol_skills = set(s.lower() for s in volunteer.skills)
        req_skills = set(s.lower() for s in required_skills)
        overlap = vol_skills & req_skills
        skill_match = (len(overlap) / len(req_skills)) * 30 if req_skills else 30
    else:
        skill_match = 15   # Neutral score when no skill requirement
    scores["skill_match"] = round(skill_match, 2)

    # ── Availability (20pts) ──────────────────────────────────────────────────
    from app.core.constants import AvailabilityStatus
    if volunteer.availability_status == AvailabilityStatus.available:
        availability = 20
    elif volunteer.availability_status == AvailabilityStatus.busy:
        availability = 10
    else:
        availability = 0
    scores["availability"] = availability

    # ── Distance (20pts) — closer = higher score ──────────────────────────────
    if (volunteer.latitude and volunteer.longitude and case.latitude and case.longitude):
        dist_km = haversine_distance_km(
            float(volunteer.latitude), float(volunteer.longitude),
            float(case.latitude), float(case.longitude),
        )
        distance = max(0, 20 * (1 - dist_km / 50))   # 0 pts at 50km+
    else:
        distance = 10   # Unknown location gets neutral score
    scores["distance"] = round(distance, 2)

    # ── Language Match (10pts) ────────────────────────────────────────────────
    languages = volunteer.languages or []
    scores["language_match"] = 10 if languages else 5

    # ── Transport (10pts) ─────────────────────────────────────────────────────
    scores["transport"] = 10 if volunteer.has_transport else 5

    # ── Reliability (5pts) ────────────────────────────────────────────────────
    scores["reliability"] = round((float(volunteer.reliability_score) / 10) * 5, 2)

    # ── Workload Penalty (5pts) ───────────────────────────────────────────────
    active = volunteer.active_assignment_count
    if active == 0:
        workload = 5
    elif active == 1:
        workload = 4
    elif active == 2:
        workload = 2
    else:
        workload = 0
    scores["workload"] = workload

    scores["total"] = round(sum(scores.values()), 2)
    return scores


class AllocationService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.org_id = current_user.organization_id

    def recommend(self, case_id: uuid.UUID) -> AllocationRecommendResponse:
        """Score all available volunteers and return top 5 recommendations."""
        case = self.db.get(Case, case_id)
        if not case or case.organization_id != self.org_id:
            raise ValueError("Case not found")

        from app.core.constants import AvailabilityStatus
        volunteers = self.db.execute(
            select(Volunteer).where(
                Volunteer.organization_id == self.org_id,
                Volunteer.availability_status.in_([
                    AvailabilityStatus.available,
                    AvailabilityStatus.busy,
                ]),
            )
        ).scalars().all()

        if not volunteers:
            return AllocationRecommendResponse(
                case_id=case_id,
                recommendations=[],
                conflict_warnings=["No available volunteers found for this organization."],
            )

        # Extract required skills from case's resource_needed field
        required_skills: list[str] = []
        if case.resource_needed:
            for r in case.resource_needed:
                if isinstance(r, dict) and r.get("item"):
                    required_skills.append(r["item"])

        # Score every volunteer and sort
        scored = [
            (vol, compute_allocation_score(vol, case, required_skills))
            for vol in volunteers
        ]
        scored.sort(key=lambda x: x[1]["total"], reverse=True)
        top5 = scored[:5]

        # Generate human-readable explanations via LLM (gracefully degrades if unavailable)
        from app.integrations.llm.openai_client import generate_allocation_explanation

        recommendations = []
        for vol, breakdown in top5:
            explanation = generate_allocation_explanation(
                case_summary={
                    "title": case.title,
                    "category": case.category.value,
                    "urgency": case.urgency_level.value,
                    "location": case.location_name,
                },
                volunteer_profile={
                    "name": vol.name,
                    "skills": vol.skills or [],
                    "languages": vol.languages or [],
                    "has_transport": vol.has_transport,
                    "reliability": float(vol.reliability_score),
                    "active_assignments": vol.active_assignment_count,
                },
                score_breakdown=breakdown,
            )
            recommendations.append(AllocationRecommendation(
                volunteer_id=vol.id,
                volunteer_name=vol.name,
                allocation_score=breakdown["total"],
                reasoning=breakdown,
                explanation=explanation,
            ))

        warnings = []
        if top5 and top5[0][1]["total"] < 40:
            warnings.append("Low allocation scores — consider recruiting more volunteers.")

        return AllocationRecommendResponse(
            case_id=case_id,
            recommendations=recommendations,
            conflict_warnings=warnings,
        )

    def conflict_check(self, case_id: uuid.UUID) -> dict[str, Any]:
        """
        Check operational conflicts for a case:
        - Inventory items out of stock for needed resources
        """
        case = self.db.get(Case, case_id)
        if not case or case.organization_id != self.org_id:
            raise ValueError("Case not found")

        conflicts = []
        if case.resource_needed:
            from app.models.inventory import InventoryItem
            from app.core.constants import InventoryStatus
            for need in case.resource_needed:
                if isinstance(need, dict):
                    item_type = need.get("item", "")
                    items = self.db.execute(
                        select(InventoryItem).where(
                            InventoryItem.organization_id == self.org_id,
                            InventoryItem.item_name.ilike(f"%{item_type}%"),
                        )
                    ).scalars().all()
                    if not items:
                        conflicts.append(f"No inventory found for '{item_type}'")
                    elif all(i.status == InventoryStatus.out_of_stock for i in items):
                        conflicts.append(f"Resource '{item_type}' is out of stock")

        return {
            "case_id": str(case_id),
            "conflicts": conflicts,
            "has_conflicts": len(conflicts) > 0,
        }
