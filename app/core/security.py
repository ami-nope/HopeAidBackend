"""
app/core/security.py — JWT token creation/verification and password hashing.

Access tokens: short-lived (30 min), signed JWT.
Refresh tokens: long-lived (7 days), UUID stored in Redis.
Passwords: PBKDF2-SHA256 hashed via passlib.

Everything here is 100% synchronous — no async, no await.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

import redis
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ─── Password Hashing ─────────────────────────────────────────────────────────
# PBKDF2-SHA256 is a secure one-way hash — you can verify but not reverse it.

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-SHA256."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check that a plaintext password matches the stored password hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT Access Token ─────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str,
    organization_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    The token payload contains:
      sub       — user ID (UUID string)
      role      — user's role (for RBAC)
      org_id    — organization ID (for multi-tenancy scoping)
      exp       — expiry timestamp
      type      — always "access" (to distinguish from refresh tokens)
    """
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": subject,
        "role": role,
        "org_id": organization_id,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Raises JWTError if invalid, expired, or wrong type.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


# ─── Refresh Token (Redis-backed) ─────────────────────────────────────────────
# Refresh tokens are NOT JWTs. They are random UUIDs stored in Redis with a TTL.
# When a user logs out, we delete the Redis key → token is immediately invalid.

REFRESH_TOKEN_PREFIX = "refresh_token:"


def create_refresh_token(user_id: str, redis_client: redis.Redis) -> str:
    """
    Generate a random refresh token and store it in Redis with an expiry TTL.

    Redis key:   refresh_token:<uuid>
    Redis value: <user_id>
    Redis TTL:   7 days (configurable via settings)
    """
    token = str(uuid.uuid4())
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    # setex = SET with EXpiry
    redis_client.setex(f"{REFRESH_TOKEN_PREFIX}{token}", ttl_seconds, user_id)
    return token


def verify_refresh_token(token: str, redis_client: redis.Redis) -> Optional[str]:
    """
    Look up a refresh token in Redis.

    Returns the user_id if the token is valid, or None if expired/not found.
    """
    user_id = redis_client.get(f"{REFRESH_TOKEN_PREFIX}{token}")
    return user_id  # Already a str because decode_responses=True in Redis client


def revoke_refresh_token(token: str, redis_client: redis.Redis) -> None:
    """Delete a refresh token from Redis (used on logout)."""
    redis_client.delete(f"{REFRESH_TOKEN_PREFIX}{token}")
