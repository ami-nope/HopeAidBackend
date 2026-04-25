"""app/tests/test_volunteers.py — Volunteer CRUD and availability tests."""

import pytest


@pytest.mark.asyncio
async def test_create_volunteer(client, admin_headers):
    resp = await client.post("/api/v1/volunteers", headers=admin_headers, json={
        "name": "Dr. Test Volunteer",
        "phone": "+91-9876543210",
        "email": "testvol@volunteer.org",
        "skills": ["first_aid", "medical"],
        "languages": ["en", "hi"],
        "has_transport": True,
        "has_medical_training": True,
        "duty_type": "full_time",
        "current_location_name": "Chennai",
        "latitude": 13.0827,
        "longitude": 80.2707,
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Dr. Test Volunteer"
    assert data["skills"] == ["first_aid", "medical"]
    assert data["reliability_score"] == 5.0


@pytest.mark.asyncio
async def test_list_volunteers(client, admin_headers):
    resp = await client.get("/api/v1/volunteers", headers=admin_headers)
    assert resp.status_code == 200
    assert "data" in resp.json()


@pytest.mark.asyncio
async def test_add_availability(client, admin_headers):
    # Create volunteer first
    create_resp = await client.post("/api/v1/volunteers", headers=admin_headers, json={
        "name": "Availability Test Vol",
        "duty_type": "part_time",
    })
    vol_id = create_resp.json()["data"]["id"]

    # Add availability slot
    slot_resp = await client.post(
        f"/api/v1/volunteers/{vol_id}/availability",
        headers=admin_headers,
        json={
            "day_of_week": 0,  # Monday
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
    )
    assert slot_resp.status_code == 201
    assert slot_resp.json()["data"]["day_of_week"] == 0
