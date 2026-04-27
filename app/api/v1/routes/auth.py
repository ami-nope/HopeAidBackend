"""app/api/v1/routes/auth.py — Authentication endpoints. All sync."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.constants import UserRole
from app.core.permissions import has_permissions, list_permissions_for_role, role_label
from app.db.session import get_db, get_redis
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import APIResponse, MessageResponse
from app.services.auth_service import AuthRateLimitError, AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=APIResponse[UserOut], status_code=201)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Register a new user account within an organization."""
    role_permission_map = {
        UserRole.admin: "users:create_org_admin",
        UserRole.org_manager: "users:create_org_manager",
        UserRole.volunteer: "users:create_volunteer",
        UserRole.field_coordinator: "users:create_volunteer",
        UserRole.reviewer: "users:create_volunteer",
    }
    required_permission = role_permission_map.get(data.role)
    if not required_permission:
        raise HTTPException(status_code=400, detail="Unsupported role")
    if not has_permissions(current_user.role, {required_permission}):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    is_super_admin = current_user.role == UserRole.super_admin
    is_global_super_admin = is_super_admin and current_user.organization_id is None
    if data.role == UserRole.admin and not is_super_admin:
        raise HTTPException(status_code=403, detail="Only DEVADMIN can create org admin accounts")
    if not is_global_super_admin and data.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot create users for another organization")

    try:
        service = AuthService(db, redis)
        user = service.register(data)
        db.commit()
        db.refresh(user)
        return {"success": True, "data": UserOut.model_validate(user), "message": "User registered successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=APIResponse[TokenResponse])
def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """Authenticate and receive JWT access + refresh tokens."""
    try:
        service = AuthService(db, redis)
        client_ip = request.client.host if request.client else None
        tokens = service.login(data, client_ip=client_ip)
        db.commit()
        return {"success": True, "data": tokens}
    except AuthRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=APIResponse[TokenResponse])
def refresh_tokens(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """Exchange a valid refresh token for new access + refresh tokens."""
    try:
        service = AuthService(db, redis)
        tokens = service.refresh_tokens(data.refresh_token)
        db.commit()
        return {"success": True, "data": tokens}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout", response_model=MessageResponse)
def logout(
    data: RefreshRequest,
    redis=Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Revoke the current refresh token (logout)."""
    from app.core.security import revoke_refresh_token
    revoke_refresh_token(data.refresh_token, redis)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=APIResponse[MeResponse])
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the currently authenticated user profile."""
    org_name = None
    if current_user.organization_id:
        from app.models.organization import Organization
        org = db.get(Organization, current_user.organization_id)
        if org:
            org_name = org.name

    return {
        "success": True,
        "data": MeResponse(
            user=UserOut.model_validate(current_user),
            organization_name=org_name,
            role_label=role_label(current_user.role),
            permissions=sorted(list_permissions_for_role(current_user.role)),
        ),
    }
