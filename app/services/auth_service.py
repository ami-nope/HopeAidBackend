"""
app/services/auth_service.py — Authentication service.

Handles: registration, login, token generation, refresh, logout.

Synchronous — no async, no await. Redis and DB calls are all sync.
"""

import uuid
from datetime import UTC, datetime
from typing import Optional

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

logger = get_logger(__name__)

FAILED_EMAIL_PREFIX = "auth:failed:email:"
FAILED_IP_PREFIX = "auth:failed:ip:"
LOCK_EMAIL_PREFIX = "auth:lock:email:"
LOCK_IP_PREFIX = "auth:lock:ip:"


class AuthRateLimitError(ValueError):
    """Raised when login is temporarily blocked due to repeated failures."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        super().__init__("Too many login attempts. Please wait and try again.")


class AuthService:
    def __init__(self, db: Session, redis_client: redis.Redis):
        # db — PostgreSQL session
        # redis_client — for storing/verifying refresh tokens
        self.db = db
        self.redis = redis_client

    def _redis_call(self, method_name: str, *args):
        """Best-effort Redis call for auth guard logic."""
        try:
            method = getattr(self.redis, method_name)
            return method(*args)
        except Exception as exc:
            logger.warning(
                "Redis auth guard operation failed",
                method=method_name,
                error=str(exc),
            )
            return None

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _normalize_client_ip(client_ip: Optional[str]) -> str:
        return client_ip.strip() if client_ip else "unknown"

    def _auth_keys(self, email: str, client_ip: Optional[str]) -> dict[str, str]:
        safe_ip = self._normalize_client_ip(client_ip)
        return {
            "email_failures": f"{FAILED_EMAIL_PREFIX}{email}",
            "ip_failures": f"{FAILED_IP_PREFIX}{safe_ip}",
            "email_lock": f"{LOCK_EMAIL_PREFIX}{email}",
            "ip_lock": f"{LOCK_IP_PREFIX}{safe_ip}",
        }

    def _increment_fail_counter(self, key: str, window_seconds: int) -> Optional[int]:
        count = self._redis_call("incr", key)
        if count is None:
            return None

        try:
            count_int = int(count)
        except (TypeError, ValueError):
            return None

        ttl_raw = self._redis_call("ttl", key)
        try:
            ttl = int(ttl_raw) if ttl_raw is not None else -1
        except (TypeError, ValueError):
            ttl = -1
        if count_int == 1 or ttl < 0:
            self._redis_call("expire", key, window_seconds)
        return count_int

    def _active_lock_ttl(self, lock_key: str) -> int:
        ttl_raw = self._redis_call("ttl", lock_key)
        if ttl_raw is None:
            return 0
        try:
            ttl = int(ttl_raw)
        except (TypeError, ValueError):
            return 0
        return ttl if ttl > 0 else 0

    def _assert_login_allowed(self, email: str, client_ip: Optional[str]) -> None:
        keys = self._auth_keys(email, client_ip)
        email_lock_ttl = self._active_lock_ttl(keys["email_lock"])
        ip_lock_ttl = self._active_lock_ttl(keys["ip_lock"])
        retry_after = max(email_lock_ttl, ip_lock_ttl)
        if retry_after > 0:
            raise AuthRateLimitError(retry_after)

    def _record_failed_login(self, email: str, client_ip: Optional[str]) -> None:
        keys = self._auth_keys(email, client_ip)

        email_failures = self._increment_fail_counter(
            keys["email_failures"],
            settings.AUTH_FAILURE_WINDOW_SECONDS,
        )
        ip_failures = self._increment_fail_counter(
            keys["ip_failures"],
            settings.AUTH_FAILURE_WINDOW_SECONDS,
        )

        if (
            email_failures is not None
            and email_failures >= settings.AUTH_MAX_FAILED_ATTEMPTS_PER_EMAIL
        ):
            self._redis_call("setex", keys["email_lock"], settings.AUTH_LOCKOUT_SECONDS, "1")

        if (
            ip_failures is not None
            and ip_failures >= settings.AUTH_MAX_FAILED_ATTEMPTS_PER_IP
        ):
            self._redis_call("setex", keys["ip_lock"], settings.AUTH_LOCKOUT_SECONDS, "1")

    def _clear_failed_login_state(self, email: str, client_ip: Optional[str]) -> None:
        keys = self._auth_keys(email, client_ip)
        for key in (
            keys["email_failures"],
            keys["ip_failures"],
            keys["email_lock"],
            keys["ip_lock"],
        ):
            self._redis_call("delete", key)

    def register(self, data: RegisterRequest) -> User:
        """
        Create a new user account.

        Validates:
          - Organization exists
          - Email is not already registered
        """
        # Check organization exists
        org = self.db.get(Organization, data.organization_id)
        if not org:
            raise ValueError("Organization not found")

        # Check email uniqueness
        existing = self.db.execute(
            select(User).where(User.email == data.email.lower())
        ).scalars().first()
        if existing:
            raise ValueError("Email already registered")

        user = User(
            organization_id=data.organization_id,
            name=data.name,
            email=data.email.lower(),
            phone=data.phone,
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()   # Gets the generated ID without committing

        logger.info("User registered", user_id=str(user.id), email=user.email)
        return user

    def login(self, data: LoginRequest, client_ip: Optional[str] = None) -> TokenResponse:
        """
        Authenticate user and return JWT access + Redis-backed refresh tokens.
        """
        normalized_email = self._normalize_email(data.email)
        self._assert_login_allowed(normalized_email, client_ip)

        user = self.db.execute(
            select(User).where(User.email == normalized_email)
        ).scalars().first()

        if not user or not verify_password(data.password, user.hashed_password):
            self._record_failed_login(normalized_email, client_ip)
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        self._clear_failed_login_state(normalized_email, client_ip)

        # Record last login time
        user.last_login_at = datetime.now(UTC)
        self.db.flush()

        org_id = str(user.organization_id) if user.organization_id else ""
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            organization_id=org_id,
        )
        # Store refresh token in Redis with 7-day TTL
        refresh_token = create_refresh_token(str(user.id), self.redis)

        logger.info("User logged in", user_id=str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Issue new access token from a valid refresh token (token rotation)."""
        user_id = verify_refresh_token(refresh_token, self.redis)
        if not user_id:
            raise ValueError("Invalid or expired refresh token")

        user = self.db.get(User, uuid.UUID(user_id))
        if not user or not user.is_active:
            raise ValueError("User not found or deactivated")

        # Revoke old token, issue new ones
        revoke_refresh_token(refresh_token, self.redis)
        org_id = str(user.organization_id) if user.organization_id else ""
        new_access = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            organization_id=org_id,
        )
        new_refresh = create_refresh_token(str(user.id), self.redis)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def logout(self, refresh_token: str) -> None:
        """Revoke refresh token from Redis — user is immediately logged out."""
        revoke_refresh_token(refresh_token, self.redis)
        logger.info("Refresh token revoked")

    def get_current_user(self, user_id: str) -> Optional[User]:
        """Fetch user by ID string."""
        return self.db.get(User, uuid.UUID(user_id))
