"""app/api/v1/router.py — Aggregates all route files into a single v1 router."""

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    ai,
    alerts,
    allocation,
    auth,
    households,
    inventory,
    organizations,
    reports,
    uploads,
    volunteers,
    cases,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(cases.router)
api_router.include_router(households.router)
api_router.include_router(volunteers.router)
api_router.include_router(inventory.router)
api_router.include_router(uploads.router)
api_router.include_router(ai.router)
api_router.include_router(allocation.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(alerts.router)
