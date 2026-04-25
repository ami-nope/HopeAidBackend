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


class AuthService:
    def __init__(self, db: Session, redis_client: redis.Redis):
        # db — PostgreSQL session
        # redis_client — for storing/verifying refresh tokens
        self.db = db
        self.redis = redis_client

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

    def login(self, data: LoginRequest) -> TokenResponse:
        """
        Authenticate user and return JWT access + Redis-backed refresh tokens.
        """
        user = self.db.execute(
            select(User).where(User.email == data.email.lower())
        ).scalars().first()

        if not user or not verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

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

        from app.core.config import settings
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

        from app.core.config import settings
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
