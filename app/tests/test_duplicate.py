"""app/tests/test_duplicate.py — Tests for duplicate detection logic."""

from app.utils.duplicate_detector import compute_duplicate_confidence, is_likely_duplicate


def test_exact_phone_match():
    """Same phone number should yield high confidence."""
    new_case = {"contact_phone": "+91-9876543210", "title": "Flood case", "household_name": "Kumar Family"}
    existing = {"contact_phone": "+91-9876543210", "title": "Flood victims", "household_name": "Kumar Household"}
    score = compute_duplicate_confidence(new_case, existing)
    assert score >= 60, f"Expected high score for phone match, got {score}"


def test_similar_title_and_name():
    """Similar household name and title should yield moderate confidence."""
    new_case = {"title": "Food needed for Kumar family after flood", "household_name": "Kumar Family"}
    existing = {"title": "Kumar family needs food assistance", "household_name": "Kumar Family"}
    score = compute_duplicate_confidence(new_case, existing)
    assert score >= 30


def test_no_match():
    """Completely different cases should yield low confidence."""
    new_case = {"contact_phone": "+91-1111111111", "title": "Medical emergency Surat", "household_name": "Patel"}
    existing = {"contact_phone": "+91-9999999999", "title": "Food shortage Odisha", "household_name": "Dash Family"}
    score = compute_duplicate_confidence(new_case, existing)
    assert score < 30


def test_location_proximity():
    """Same latitude/longitude should contribute to duplicate score."""
    new_case = {"title": "Case A", "latitude": 13.0827, "longitude": 80.2707}
    existing = {"title": "Case B", "latitude": 13.0828, "longitude": 80.2708}
    score = compute_duplicate_confidence(new_case, existing)
    assert score > 0


def test_is_likely_duplicate_threshold():
    assert is_likely_duplicate(70.0) is True
    assert is_likely_duplicate(50.0) is False
    assert is_likely_duplicate(65.0) is True
    assert is_likely_duplicate(64.9) is False
