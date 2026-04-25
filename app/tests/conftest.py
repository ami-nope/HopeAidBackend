"""
app/tests/conftest.py — Pytest fixtures for the HopeAid test suite.

Uses an in-memory SQLite database for speed, with async support.
All tests run in isolated transactions that are rolled back after each test.
"""

import uuid
from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.constants import OrgStatus, UserRole
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db, get_redis
from app.main import app
from app.models.organization import Organization
from app.models.user import User

# ─── Test Database (SQLite async) ────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_hopeaid.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables once before tests, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Per-test async DB session."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ─── Mock Redis ───────────────────────────────────────────────────────────────

class MockRedis:
    """In-memory mock for Redis used in tests."""
    def __init__(self):
        self._store: dict = {}

    async def setex(self, key: str, ttl: int, value: str):
        self._store[key] = value

    async def get(self, key: str):
        return self._store.get(key)

    async def delete(self, key: str):
        self._store.pop(key, None)


@pytest_asyncio.fixture
async def mock_redis():
    return MockRedis()


# ─── Test Client ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis: MockRedis) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with DB and Redis overridden for testing."""
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Test Data Factories ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession) -> Organization:
    org = Organization(
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
        status=OrgStatus.active,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession, test_org: Organization) -> User:
    user = User(
        organization_id=test_org.id,
        name="Test Admin",
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Test@1234"),
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_volunteer_user(db_session: AsyncSession, test_org: Organization) -> User:
    user = User(
        organization_id=test_org.id,
        name="Test Volunteer",
        email=f"vol-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Test@1234"),
        role=UserRole.volunteer,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, test_org: Organization, test_admin: User) -> str:
    """Get auth token for test admin."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": test_admin.email,
        "password": "Test@1234",
    })
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


@pytest_asyncio.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
