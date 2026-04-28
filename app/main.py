"""
app/main.py — FastAPI application factory (fully synchronous).

Entry point for HopeAid backend.
Configures: CORS, rate limiting, middleware, exception handlers, and routes.
No async lifespan needed — startup checks use sync DB connection.
"""

import uuid
from datetime import UTC, datetime
from threading import Lock
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.base import Base
from app.db.session import engine, get_redis

# Set up structured logging immediately when the module loads
setup_logging()
logger = get_logger(__name__)


# ─── Rate Limiter ─────────────────────────────────────────────────────────────
# Controls how many requests per IP are allowed per minute.

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

_tables_initialized = False
_tables_init_lock = Lock()


def _import_orm_models() -> None:
    """Import ORM modules so model tables are registered in Base.metadata."""
    import app.models as models  # noqa: F401

    _ = models.__all__


def _create_tables_once() -> None:
    """Create tables once per process, after all model metadata is loaded."""
    global _tables_initialized

    if _tables_initialized:
        return

    with _tables_init_lock:
        if _tables_initialized:
            return

        _import_orm_models()
        Base.metadata.create_all(bind=engine)
        _tables_initialized = True


def _to_json_safe(value: Any) -> Any:
    """Recursively convert objects into JSON-serializable values."""
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _dependency_payload(ok: bool | None = None, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    if error:
        payload["error"] = error
    return payload


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application.

    Separated into a factory function so tests can create fresh instances.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production-ready backend for HopeAid — humanitarian aid management platform",
        # Hide docs in production for security
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )
    app.state.dependency_checks = {
        "database": _dependency_payload(),
        "redis": _dependency_payload(),
        "tables": _dependency_payload(),
    }

    # ── Startup event ────────────────────────────────────────────────────────
    @app.on_event("startup")
    def on_startup():
        """Verify external dependencies without blocking process liveness."""
        logger.info(
            "HopeAid backend starting",
            version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT,
        )
        dependency_checks = app.state.dependency_checks

        try:
            from sqlalchemy import text

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            dependency_checks["database"] = _dependency_payload(ok=True)
            logger.info("Database connectivity verified")
        except Exception as e:
            dependency_checks["database"] = _dependency_payload(ok=False, error=str(e))
            dependency_checks["tables"] = _dependency_payload(ok=False, error="Skipped because database check failed")
            logger.warning("Database connectivity check failed during startup", error=str(e))
        else:
            try:
                if settings.should_auto_create_tables_on_startup:
                    _create_tables_once()
                    dependency_checks["tables"] = _dependency_payload(ok=True)
                    logger.info("Database tables ensured")
                else:
                    dependency_checks["tables"] = _dependency_payload(ok=True)
                    logger.info("Automatic table creation skipped")
            except Exception as e:
                dependency_checks["tables"] = _dependency_payload(ok=False, error=str(e))
                logger.warning("Database table initialization failed during startup", error=str(e))

        try:
            get_redis().ping()
            dependency_checks["redis"] = _dependency_payload(ok=True)
            logger.info("Redis connectivity verified")
        except Exception as e:
            dependency_checks["redis"] = _dependency_payload(ok=False, error=str(e))
            logger.warning("Redis connectivity check failed during startup", error=str(e))

    @app.on_event("shutdown")
    def on_shutdown():
        """Dispose connection pool on shutdown."""
        logger.info("HopeAid backend shutting down")
        engine.dispose()

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Allow specified origins (from .env) to call the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Request ID Middleware ─────────────────────────────────────────────────
    # Adds a unique X-Request-ID to every request for tracing in logs
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Exception Handlers ────────────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Return structured JSON for Pydantic validation errors."""
        details = _to_json_safe(exc.errors())

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "Validation error",
                "details": details,
                "code": "VALIDATION_ERROR",
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Catch-all handler — logs the error and returns a safe 500 response."""
        logger.error(
            "Unhandled exception",
            path=str(request.url),
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # ── Health Check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health():
        checks = getattr(app.state, "dependency_checks", {})
        has_failures = any(check.get("ok") is False for check in checks.values())
        return {
            "status": "degraded" if has_failures else "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        }

    @app.get("/ready", tags=["Health"])
    def ready():
        checks = getattr(app.state, "dependency_checks", {})
        has_failures = any(check.get("ok") is False for check in checks.values())
        payload = {
            "status": "ready" if not has_failures else "not_ready",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        }
        if has_failures:
            return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
        return payload

    @app.get("/", tags=["Root"])
    def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }

    return app


app = create_app()
