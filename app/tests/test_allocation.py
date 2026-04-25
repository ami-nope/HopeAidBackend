"""app/tests/test_allocation.py — Allocation scoring unit tests."""

from unittest.mock import MagicMock

from app.services.allocation_service import compute_allocation_score
from app.core.constants import AvailabilityStatus, UrgencyLevel


def make_mock_volunteer(
    skills=None,
    languages=None,
    has_transport=True,
    availability=AvailabilityStatus.available,
    reliability=8.0,
    active_assignments=0,
    lat=13.0,
    lon=80.0,
):
    vol = MagicMock()
    vol.skills = skills or ["first_aid"]
    vol.languages = languages or ["en"]
    vol.has_transport = has_transport
    vol.availability_status = availability
    vol.reliability_score = reliability
    vol.active_assignment_count = active_assignments
    vol.latitude = lat
    vol.longitude = lon
    return vol


def make_mock_case(lat=13.0, lon=80.0, resource_needed=None):
    case = MagicMock()
    case.latitude = lat
    case.longitude = lon
    case.urgency_level = UrgencyLevel.high
    case.resource_needed = resource_needed or []
    return case


def test_perfect_match_scores_high():
    """Volunteer perfectly matching case should score above 80."""
    vol = make_mock_volunteer(skills=["first_aid", "medical"], lat=13.0827, lon=80.2707)
    case = make_mock_case(lat=13.0827, lon=80.2707, resource_needed=[{"item": "first_aid"}])
    scores = compute_allocation_score(vol, case, required_skills=["first_aid"])
    assert scores["total"] > 70, f"Expected >70 for perfect match, got {scores['total']}"


def test_far_volunteer_scores_lower():
    """Volunteer 200km away should score lower than nearby volunteer."""
    near_vol = make_mock_volunteer(lat=13.08, lon=80.27)
    far_vol = make_mock_volunteer(lat=15.50, lon=78.00)
    case = make_mock_case(lat=13.08, lon=80.27)

    near_scores = compute_allocation_score(near_vol, case)
    far_scores = compute_allocation_score(far_vol, case)
    assert near_scores["distance"] > far_scores["distance"]


def test_busy_volunteer_penalized():
    """Volunteer with 3+ active assignments should score 0 for workload."""
    overloaded = make_mock_volunteer(active_assignments=3)
    idle = make_mock_volunteer(active_assignments=0)
    case = make_mock_case()
    assert compute_allocation_score(overloaded, case)["workload"] == 0
    assert compute_allocation_score(idle, case)["workload"] == 5


def test_unavailable_volunteer_scores_zero_availability():
    """Unavailable volunteer should score 0 on availability."""
    vol = make_mock_volunteer(availability=AvailabilityStatus.unavailable)
    case = make_mock_case()
    assert compute_allocation_score(vol, case)["availability"] == 0


def test_total_capped_at_100():
    """Score total should never exceed 100."""
    vol = make_mock_volunteer()
    case = make_mock_case()
    scores = compute_allocation_score(vol, case)
    assert scores["total"] <= 100
