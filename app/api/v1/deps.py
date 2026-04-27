"""
app/api/v1/deps.py — FastAPI shared dependencies for all routes.

These are functions that FastAPI calls automatically via Depends().
They are all synchronous — FastAPI runs sync Depends in a threadpool.

Provides:
  get_current_user()  — decode JWT and return authenticated User
  require_roles()     — RBAC guard (raises 403 if wrong role)
  get_client_ip()     — extract real client IP from request headers
"""

from typing import Optional, Set
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.constants import UserRole
from app.core.logging import get_logger
from app.core.permissions import has_permissions
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

logger = get_logger(__name__)

# Bearer token scheme — reads the "Authorization: Bearer <token>" header
security = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT Bearer token and return the authenticated User object.

    Raises HTTP 401 if:
    - Token is missing, invalid, or expired
    - User does not exist or is deactivated
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode and validate the JWT
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user from database by ID
    user = db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise credentials_exception

    return user


def require_roles(*roles: UserRole):
    """
    FastAPI dependency factory for role-based access control (RBAC).

    Usage:
        @router.post("/approve")
        def approve(user = Depends(require_roles(UserRole.admin, UserRole.org_manager))):
            ...

    Raises HTTP 403 if the current user's role is not in the allowed list.
    """
    allowed: Set[UserRole] = set(roles)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed]}",
            )
        return current_user

    return _check


def require_permissions(*permissions: str):
    """
    FastAPI dependency factory for permission-based access control.
    """
    required_permissions: Set[str] = set(permissions)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if not has_permissions(current_user.role, required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required permissions: {sorted(required_permissions)}",
            )
        return current_user

    return _check


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Simple alias for get_current_user — used where any auth is sufficient."""
    return current_user


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP, handling X-Forwarded-For proxy headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None
