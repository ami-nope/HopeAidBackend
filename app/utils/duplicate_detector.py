"""
app/utils/duplicate_detector.py — Fuzzy duplicate detection for cases.

Checks:
1. Exact phone match (contact_phone on household)
2. Fuzzy household name similarity (rapidfuzz token_sort_ratio)
3. Location proximity (within ~500m using Haversine)
4. Title text similarity

Returns a confidence score 0-100 and matched case IDs.
"""

import math

from rapidfuzz import fuzz


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points in kilometers.
    Uses Haversine formula — sufficient accuracy for case de-duplication.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_duplicate_confidence(
    new_case: dict,
    existing_case: dict,
) -> float:
    """
    Compare two case-like dicts and return a duplicate confidence score (0-100).

    Expected keys in each dict:
    - contact_phone (optional str)
    - household_name (optional str)
    - location_name (optional str)
    - latitude (optional float)
    - longitude (optional float)
    - title (str)
    """
    score = 0.0
    max_score = 0.0

    # ── Phone exact match (weight: 40) ─────────────────────────────────────
    max_score += 40
    phone1 = (new_case.get("contact_phone") or "").strip()
    phone2 = (existing_case.get("contact_phone") or "").strip()
    if phone1 and phone2 and phone1 == phone2:
        score += 40

    # ── Household name similarity (weight: 25) ──────────────────────────────
    max_score += 25
    name1 = new_case.get("household_name") or ""
    name2 = existing_case.get("household_name") or ""
    if name1 and name2:
        name_sim = fuzz.token_sort_ratio(name1.lower(), name2.lower())
        score += (name_sim / 100) * 25

    # ── Title text similarity (weight: 20) ─────────────────────────────────
    max_score += 20
    title1 = new_case.get("title") or ""
    title2 = existing_case.get("title") or ""
    if title1 and title2:
        title_sim = fuzz.token_sort_ratio(title1.lower(), title2.lower())
        score += (title_sim / 100) * 20

    # ── Location proximity (weight: 15) — within 1km = full score ──────────
    max_score += 15
    lat1, lon1 = new_case.get("latitude"), new_case.get("longitude")
    lat2, lon2 = existing_case.get("latitude"), existing_case.get("longitude")
    if all(v is not None for v in [lat1, lon1, lat2, lon2]):
        dist_km = haversine_distance_km(lat1, lon1, lat2, lon2)
        if dist_km <= 1.0:
            score += max(0, (1 - dist_km) * 15)
    else:
        # Fall back to string location similarity
        loc1 = new_case.get("location_name") or ""
        loc2 = existing_case.get("location_name") or ""
        if loc1 and loc2:
            loc_sim = fuzz.partial_ratio(loc1.lower(), loc2.lower())
            score += (loc_sim / 100) * 15

    # Normalize to 100
    if max_score == 0:
        return 0.0
    return round((score / max_score) * 100, 2)


def is_likely_duplicate(confidence: float, threshold: float = 65.0) -> bool:
    """Return True if confidence exceeds the duplicate threshold."""
    return confidence >= threshold
