"""app/tests/test_cases.py — Tests for case creation, status transitions, and risk scoring."""

import pytest


@pytest.mark.asyncio
async def test_create_case(client, admin_headers, test_org):
    resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Food shortage — 10 families affected",
        "category": "food",
        "urgency_level": "high",
        "disaster_type": "flood",
        "number_of_people_affected": 40,
        "location_name": "Test Village",
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["case_number"].startswith("TEST")
    assert data["risk_score"] is not None
    assert data["status"] == "new"
    assert data["geocode_status"] == "pending"
    assert data["next_weather_check_at"] is not None


@pytest.mark.asyncio
async def test_create_case_validation(client, admin_headers):
    # Title too short
    resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "AB",
        "category": "food",
        "urgency_level": "medium",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_case_without_location_skips_geocode_queue(client, admin_headers):
    resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "No location case",
        "category": "food",
        "urgency_level": "medium",
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["geocode_status"] == "not_requested"
    assert data["next_weather_check_at"] is None


@pytest.mark.asyncio
async def test_list_cases(client, admin_headers):
    resp = await client.get("/api/v1/cases", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_list_cases_with_search_query(client, admin_headers):
    create_resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Medical support needed in Sector 7",
        "category": "medical",
        "urgency_level": "high",
        "location_name": "Sector 7",
    })
    assert create_resp.status_code == 201

    resp = await client.get("/api/v1/cases?q=Sector%207", headers=admin_headers)
    assert resp.status_code == 200

    titles = [item["title"] for item in resp.json()["data"]]
    assert "Medical support needed in Sector 7" in titles


@pytest.mark.asyncio
async def test_super_admin_can_list_cases_across_orgs(client, super_admin_headers, admin_headers):
    create_resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Cross-org visible case",
        "category": "food",
        "urgency_level": "medium",
    })
    assert create_resp.status_code == 201

    resp = await client.get("/api/v1/cases", headers=super_admin_headers)
    assert resp.status_code == 200
    titles = [item["title"] for item in resp.json()["data"]]
    assert "Cross-org visible case" in titles


@pytest.mark.asyncio
async def test_approve_case(client, admin_headers):
    # Create a case first
    create_resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Test approval case",
        "category": "shelter",
        "urgency_level": "medium",
    })
    assert create_resp.status_code == 201
    case_id = create_resp.json()["data"]["id"]

    # Approve it
    approve_resp = await client.post(f"/api/v1/cases/{case_id}/approve", headers=admin_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["status"] == "verified"


@pytest.mark.asyncio
async def test_reject_case(client, admin_headers):
    create_resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Test rejection case",
        "category": "food",
        "urgency_level": "low",
    })
    case_id = create_resp.json()["data"]["id"]

    reject_resp = await client.post(
        f"/api/v1/cases/{case_id}/reject",
        headers=admin_headers,
        json={"reason": "Duplicate report already exists"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_risk_score_computed(client, admin_headers):
    resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Critical flood case with many people",
        "category": "food",
        "urgency_level": "critical",
        "disaster_type": "conflict",
        "number_of_people_affected": 500,
    })
    assert resp.status_code == 201
    risk_score = resp.json()["data"]["risk_score"]
    assert risk_score >= 59, f"Expected elevated risk score for critical+conflict case, got {risk_score}"
