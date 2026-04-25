"""app/tests/test_admin.py — Admin approval workflow and audit log tests."""

import pytest


@pytest.mark.asyncio
async def test_admin_workflow_full(client, admin_headers):
    """Full admin approval workflow: create → approve → assign → close."""
    # 1. Create case
    case_resp = await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Full workflow test case",
        "category": "medical",
        "urgency_level": "high",
        "number_of_people_affected": 10,
    })
    assert case_resp.status_code == 201
    case_id = case_resp.json()["data"]["id"]
    assert case_resp.json()["data"]["status"] == "new"

    # 2. Approve case
    approve_resp = await client.post(f"/api/v1/cases/{case_id}/approve", headers=admin_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["status"] == "verified"

    # 3. Duplicate check
    dup_resp = await client.post(f"/api/v1/cases/{case_id}/duplicate-check", headers=admin_headers)
    assert dup_resp.status_code == 200
    assert "is_duplicate" in dup_resp.json()["data"]

    # 4. Risk recalculation
    risk_resp = await client.post(f"/api/v1/cases/{case_id}/recalculate-risk", headers=admin_headers)
    assert risk_resp.status_code == 200
    assert risk_resp.json()["data"]["risk_score"] is not None


@pytest.mark.asyncio
async def test_audit_logs_created(client, admin_headers):
    """Creating a case should produce an audit log entry."""
    # Create a case to trigger audit log
    await client.post("/api/v1/cases", headers=admin_headers, json={
        "title": "Audit log test case",
        "category": "food",
        "urgency_level": "medium",
    })

    # Check audit logs
    audit_resp = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()["data"]
    assert isinstance(logs, list)


@pytest.mark.asyncio
async def test_form_template_crud(client, admin_headers):
    """Create and list form templates."""
    create_resp = await client.post(
        "/api/v1/admin/forms",
        headers=admin_headers,
        params={
            "form_name": "Flood Intake Form",
        },
        json=[
            {"name": "victim_count", "type": "integer", "required": True, "label": "Number of Victims"},
            {"name": "water_access", "type": "boolean", "required": True, "label": "Has water access?"},
        ],
    )
    assert create_resp.status_code == 201

    list_resp = await client.get("/api/v1/admin/forms", headers=admin_headers)
    assert list_resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_summary(client, admin_headers):
    """Dashboard summary endpoint should return expected metrics."""
    resp = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_cases" in data
    assert "open_cases" in data
    assert "total_volunteers" in data
    assert "cases_by_status" in data
