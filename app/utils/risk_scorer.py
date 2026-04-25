"""
app/utils/risk_scorer.py — Rule-based risk score computation for cases.

Risk score formula (0-100):
  - urgency_score    (35%): critical=100, high=65, medium=35, low=10
  - disaster_score   (15%): conflict/earthquake/cyclone = high, others = medium
  - scale_score      (10%): log-normalized people affected
  - time_score       (10%): hours since report, capped at 15
  - vuln_score       (20%): pregnancy, disability, children flags from linked persons
  - essentials_score (10%): number of unmet resource categories

All weights are defined in constants.RISK_WEIGHTS.
"""

import math
from datetime import UTC, datetime
from typing import Optional

from app.core.constants import DisasterType, UrgencyLevel

# ─── Urgency Mapping ─────────────────────────────────────────────────────────

URGENCY_SCORES: dict[UrgencyLevel, float] = {
    UrgencyLevel.critical: 100.0,
    UrgencyLevel.high: 65.0,
    UrgencyLevel.medium: 35.0,
    UrgencyLevel.low: 10.0,
}

# ─── Disaster Type Risk Mapping ──────────────────────────────────────────────

DISASTER_SCORES: dict[DisasterType, float] = {
    DisasterType.conflict: 100.0,
    DisasterType.earthquake: 90.0,
    DisasterType.cyclone: 85.0,
    DisasterType.flood: 75.0,
    DisasterType.pandemic: 70.0,
    DisasterType.fire: 65.0,
    DisasterType.drought: 50.0,
    DisasterType.other: 40.0,
}


def compute_risk_score(
    urgency_level: UrgencyLevel,
    disaster_type: Optional[DisasterType],
    number_of_people_affected: int,
    created_at: datetime,
    has_vulnerable_persons: bool = False,  # pregnancy/disability/children
    vulnerable_person_count: int = 0,
    resource_needed_count: int = 0,
) -> float:
    """
    Compute a 0-100 risk score from case fields.

    Args:
        urgency_level: Case urgency
        disaster_type: Type of disaster (optional)
        number_of_people_affected: Scale
        created_at: When the case was created (for time penalty)
        has_vulnerable_persons: Whether any linked persons have vulnerability flags
        vulnerable_person_count: Count of vulnerable persons
        resource_needed_count: Number of distinct resource needs

    Returns:
        float: Risk score 0-100
    """
    # ── Urgency (35%) ───────────────────────────────────────────────────────
    urgency_score = URGENCY_SCORES.get(urgency_level, 35.0)

    # ── Disaster (15%) ──────────────────────────────────────────────────────
    disaster_score = DISASTER_SCORES.get(disaster_type, 40.0) if disaster_type else 40.0

    # ── Scale (10%) — log-normalized, capped at 100 ─────────────────────────
    scale_score = min(math.log(max(number_of_people_affected, 1) + 1) / math.log(1001) * 100, 100.0)

    # ── Time since report (10%) — hours, capped at 48h → 100 ────────────────
    hours_elapsed = (datetime.now(UTC) - created_at.replace(tzinfo=UTC if created_at.tzinfo is None else created_at.tzinfo)).total_seconds() / 3600
    time_score = min(hours_elapsed / 48 * 100, 100.0)

    # ── Vulnerability (20%) — presence and count of vulnerable persons ───────
    if has_vulnerable_persons:
        vuln_score = min(50.0 + vulnerable_person_count * 10, 100.0)
    else:
        vuln_score = 0.0

    # ── Missing Essentials (10%) — each unmet resource need adds risk ────────
    essentials_score = min(resource_needed_count * 20, 100.0)

    # ── Weighted Sum ─────────────────────────────────────────────────────────
    score = (
        urgency_score    * 0.35 +
        disaster_score   * 0.15 +
        scale_score      * 0.10 +
        time_score       * 0.10 +
        vuln_score       * 0.20 +
        essentials_score * 0.10
    )

    return round(min(max(score, 0.0), 100.0), 2)


def get_risk_explanation(
    urgency_level: UrgencyLevel,
    disaster_type: Optional[DisasterType],
    number_of_people_affected: int,
    has_vulnerable_persons: bool,
    resource_needed_count: int,
) -> dict:
    """
    Return a structured breakdown of risk score components for display.
    """
    return {
        "urgency": {
            "value": urgency_level.value,
            "score": URGENCY_SCORES.get(urgency_level, 35.0),
            "weight": "35%",
        },
        "disaster_type": {
            "value": disaster_type.value if disaster_type else "not specified",
            "score": DISASTER_SCORES.get(disaster_type, 40.0) if disaster_type else 40.0,
            "weight": "15%",
        },
        "people_affected": {
            "value": number_of_people_affected,
            "weight": "10%",
        },
        "has_vulnerable_persons": {
            "value": has_vulnerable_persons,
            "weight": "20%",
        },
        "resource_needs_count": {
            "value": resource_needed_count,
            "weight": "10%",
        },
    }
