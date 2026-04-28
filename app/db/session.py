"""
app/db/session.py — Synchronous SQLAlchemy engine and session factory.

Everything here is 100% synchronous — no async, no await.

How it works:
  1. create_engine() — opens a connection pool to PostgreSQL
  2. SessionLocal — a factory that creates new Session objects
  3. get_db() — a FastAPI dependency that opens/closes a session per request
  4. get_redis() — returns a synchronous Redis client for token storage
"""

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Database Engine ──────────────────────────────────────────────────────────
# create_engine sets up the connection pool to PostgreSQL.
# pool_pre_ping=True checks that connections are alive before using them.

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,       # Reconnect if connection dropped
    echo=settings.DEBUG,      # Log SQL queries when DEBUG=true
)

# ─── Session Factory ──────────────────────────────────────────────────────────
# SessionLocal() creates a new database Session each time it is called.
# autocommit=False: you control when to commit
# autoflush=False: prevents accidental early flushes

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Keep objects usable after commit
)


# ─── FastAPI DB Dependency ────────────────────────────────────────────────────
def get_db():
    """
    FastAPI dependency — opens a DB session, yields it, then closes it.

    Usage in a route:
        @router.get("/")
        def my_route(db: Session = Depends(get_db)):
            results = db.query(MyModel).all()
            return results
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()        # Commit on success
    except Exception:
        db.rollback()      # Roll back on any error
        raise
    finally:
        db.close()         # Always close the session


# ─── Redis Client ─────────────────────────────────────────────────────────────
# Redis is used to store refresh tokens (with TTL/expiry).
# We use the synchronous redis client here — no asyncio needed.

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """
    FastAPI dependency — returns a shared synchronous Redis client.

    The client is created once on first call and reused (connection pooling
    is handled internally by the redis library).
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,   # Always returns str, not bytes
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        )
    return _redis_client
