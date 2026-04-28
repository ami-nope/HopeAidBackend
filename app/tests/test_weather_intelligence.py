"""Weather intelligence API tests."""

import pytest


@pytest.mark.asyncio
async def test_refresh_case_location_endpoint(client, admin_headers, monkeypatch):
    create_resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Chennai flood watch",
        "category": "food",
        "urgency_level": "high",
        "location_name": "T Nagar Chennai",
    })
    assert create_resp.status_code == 201
    case_id = create_resp.json()["data"]["id"]

    from app.integrations.geocoding.open_meteo_client import OpenMeteoGeocodingClient

    def fake_geocode(self, place_name: str):
        assert place_name == "T Nagar Chennai"
        return {
            "latitude": 13.0418,
            "longitude": 80.2337,
            "district": "Chennai",
            "state": "Tamil Nadu",
            "provider": "open_meteo",
            "confidence": 88.0,
            "raw": {},
        }

    monkeypatch.setattr(OpenMeteoGeocodingClient, "geocode", fake_geocode)

    resp = await client.post(f"/api/v1/cases/{case_id}/refresh-location", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["geocode_status"] == "resolved"
    assert data["district"] == "Chennai"
    assert data["state"] == "Tamil Nadu"


@pytest.mark.asyncio
async def test_run_weather_intelligence_batch_endpoint(client, admin_headers, monkeypatch):
    from app.services.weather_intelligence_service import WeatherIntelligenceService

    def fake_scan(self, organization_id=None, limit=None):
        return {
            "scanned_cases": 3,
            "assessed_cases": 2,
            "alerts_created_or_updated": 1,
            "alerts_resolved": 0,
            "geocoded_cases": 1,
            "skipped_cases": 1,
        }

    monkeypatch.setattr(WeatherIntelligenceService, "scan_due_cases", fake_scan)

    resp = await client.post("/api/v1/alerts/intelligence/run", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["assessed_cases"] == 2
    assert data["alerts_created_or_updated"] == 1


@pytest.mark.asyncio
async def test_alerts_list_includes_weather_metadata(client, admin_headers, db_session, test_org):
    from app.core.constants import AlertType, RecipientType
    from app.models.alert import Alert

    alert = Alert(
        organization_id=test_org.id,
        type=AlertType.weather_risk,
        message="Short weather description",
        recipient_type=RecipientType.admin,
        metadata_json={
            "heading": "Volunteer travel risk near Chennai",
            "description": "Heavy rain and gusts may slow response.",
            "full_text": "Extended explanation",
            "solution": "Delay travel by 30 minutes.",
            "severity": "high",
        },
    )
    db_session.add(alert)
    db_session.commit()

    resp = await client.get("/api/v1/alerts", headers=admin_headers)
    assert resp.status_code == 200
    listed = next(item for item in resp.json()["data"] if item["id"] == str(alert.id))
    assert listed["metadata_json"]["heading"] == "Volunteer travel risk near Chennai"
    assert listed["metadata_json"]["solution"] == "Delay travel by 30 minutes."
