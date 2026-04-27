"""app/tests/test_auth.py — Tests for authentication endpoints."""

import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_register_success(client, test_org, admin_headers):
    resp = await client.post("/api/v1/auth/register", json={
        "organization_id": str(test_org.id),
        "name": "New User",
        "email": "newuser@test.com",
        "password": "Test@1234",
        "role": "field_coordinator",
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["email"] == "newuser@test.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client, test_org, test_admin, admin_headers):
    resp = await client.post("/api/v1/auth/register", json={
        "organization_id": str(test_org.id),
        "name": "Duplicate",
        "email": test_admin.email,
        "password": "Test@1234",
        "role": "field_coordinator",
    }, headers=admin_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client, test_org, admin_headers):
    resp = await client.post("/api/v1/auth/register", json={
        "organization_id": str(test_org.id),
        "name": "Weak Pass",
        "email": "weak@test.com",
        "password": "password",  # No uppercase, no digit
        "role": "field_coordinator",
    }, headers=admin_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, test_admin):
    resp = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email,
        "password": "Test@1234",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_success_with_identifier_key(client, test_admin):
    resp = await client.post("/api/v1/auth/login", json={
        "identifier": test_admin.email,
        "password": "Test@1234",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_success_with_phone_identifier(client, test_admin):
    assert test_admin.phone is not None
    resp = await client.post("/api/v1/auth/login", json={
        "identifier": test_admin.phone,
        "password": "Test@1234",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_admin):
    resp = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email,
        "password": "WrongPass@1",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password_with_phone_identifier(client, test_admin):
    assert test_admin.phone is not None
    resp = await client.post("/api/v1/auth/login", json={
        "identifier": test_admin.phone,
        "password": "WrongPass@1",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_lockout_after_repeated_failures(client, test_admin):
    payload = {
        "email": test_admin.email,
        "password": "WrongPass@1",
    }
    for _ in range(settings.AUTH_MAX_FAILED_ATTEMPTS_PER_EMAIL):
        resp = await client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 401

    locked = await client.post("/api/v1/auth/login", json=payload)
    assert locked.status_code == 429
    assert locked.headers.get("Retry-After")


@pytest.mark.asyncio
async def test_get_me(client, admin_headers):
    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "user" in data
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
