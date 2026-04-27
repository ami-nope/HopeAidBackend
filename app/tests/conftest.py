"""
app/tests/conftest.py - Shared pytest fixtures for HopeAid tests.

The API is fully synchronous, so tests use a synchronous SQLAlchemy Session.
HTTP requests remain async via httpx.AsyncClient.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from app.core.constants import OrgStatus, UserRole
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db, get_redis
from app.main import app
from app.models.organization import Organization
from app.models.user import User

# --- Test Database (SQLite sync) ------------------------------------------------

TEST_DATABASE_URL = "sqlite:///./test_hopeaid.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


@compiles(PGUUID, "sqlite")
def _compile_uuid_for_sqlite(_type, _compiler, **_kwargs):
    return "CHAR(36)"


def _strip_postgres_server_defaults_for_sqlite() -> None:
    """
    SQLite rejects Postgres-specific defaults like gen_random_uuid().
    Remove them only for sqlite-backed tests.
    """
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if not column.server_default:
                continue
            default_sql = str(column.server_default.arg).lower()
            if "gen_random_uuid" in default_sql:
                column.server_default = None


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    _strip_postgres_server_defaults_for_sqlite()
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# --- Mock Redis ----------------------------------------------------------------

class MockRedis:
    """In-memory Redis mock with TTL/counter support."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._expiry: dict[str, datetime] = {}

    def _is_expired(self, key: str) -> bool:
        expires_at = self._expiry.get(key)
        if not expires_at:
            return False
        if datetime.now(UTC) >= expires_at:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    def setex(self, key: str, ttl: int, value: str):
        self._store[key] = str(value)
        self._expiry[key] = datetime.now(UTC) + timedelta(seconds=max(0, int(ttl)))
        return True

    def get(self, key: str):
        if self._is_expired(key):
            return None
        return self._store.get(key)

    def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            existed = key in self._store
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            if existed:
                deleted += 1
        return deleted

    def incr(self, key: str):
        self._is_expired(key)
        current = self._store.get(key)
        current_value = int(current) if current is not None else 0
        next_value = current_value + 1
        self._store[key] = str(next_value)
        return next_value

    def expire(self, key: str, ttl: int):
        if self._is_expired(key):
            return False
        if key not in self._store:
            return False
        self._expiry[key] = datetime.now(UTC) + timedelta(seconds=max(0, int(ttl)))
        return True

    def ttl(self, key: str):
        if self._is_expired(key):
            return -2
        if key not in self._store:
            return -2
        expires_at = self._expiry.get(key)
        if not expires_at:
            return -1
        seconds_left = int((expires_at - datetime.now(UTC)).total_seconds())
        return max(0, seconds_left)

    def ping(self):
        return True


@pytest.fixture
def mock_redis() -> MockRedis:
    return MockRedis()


# --- Test Client ---------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session: Session, mock_redis: MockRedis):
    def override_get_db():
        yield db_session

    def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# --- Test Data Factories -------------------------------------------------------

@pytest.fixture
def test_org(db_session: Session) -> Organization:
    org = Organization(
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
        status=OrgStatus.active,
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_admin(db_session: Session, test_org: Organization) -> User:
    user = User(
        organization_id=test_org.id,
        name="Test Admin",
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Test@1234"),
        role=UserRole.admin,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_super_admin(db_session: Session) -> User:
    user = User(
        organization_id=None,
        name="Test Super Admin",
        email=f"super-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Test@1234"),
        role=UserRole.super_admin,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_volunteer_user(db_session: Session, test_org: Organization) -> User:
    user = User(
        organization_id=test_org.id,
        name="Test Volunteer",
        email=f"vol-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Test@1234"),
        role=UserRole.volunteer,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, test_org: Organization, test_admin: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_admin.email, "password": "Test@1234"},
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def super_admin_token(client: AsyncClient, test_super_admin: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": test_super_admin.email, "password": "Test@1234"},
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


@pytest.fixture
def super_admin_headers(super_admin_token: str) -> dict:
    return {"Authorization": f"Bearer {super_admin_token}"}
