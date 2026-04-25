"""
app/core/config.py — Application settings loaded from environment variables.

All secrets and config values come from environment variables (.env file).
Defaults are safe for local development only.
"""

import json
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Map of wrong driver prefixes → correct sync psycopg2 prefix
_ASYNC_TO_SYNC_DRIVERS = {
    "postgresql+asyncpg://": "postgresql+psycopg2://",
    "postgresql+aiopg://": "postgresql+psycopg2://",
    # Also handle bare postgres:// (common from cloud providers like Railway/Supabase)
    "postgres://": "postgresql+psycopg2://",
    "postgresql://": "postgresql+psycopg2://",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "HopeAid"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"   # development | staging | production
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ─── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_32_BYTES",
        description="JWT signing key — must be changed in production",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── Database ─────────────────────────────────────────────────────────────
    # Must use: postgresql+psycopg2://user:pass@host:port/dbname
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://hopeaid:hopeaid@localhost:5432/hopeaid",
        description="Sync PostgreSQL connection string using psycopg2",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """
        Auto-fix DATABASE_URL to use the psycopg2 sync driver.

        This is helpful because:
        - Cloud providers (Railway, Supabase) often give postgresql:// URLs
        - Old async config might have postgresql+asyncpg:// URLs
        - This validator silently corrects both cases
        """
        for wrong_prefix, correct_prefix in _ASYNC_TO_SYNC_DRIVERS.items():
            if v.startswith(wrong_prefix):
                return v.replace(wrong_prefix, correct_prefix, 1)
        return v

    # ─── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ─── CORS ─────────────────────────────────────────────────────────────────
    # Accept either comma-separated string or JSON list string from env.
    CORS_ORIGINS: str = "http://localhost:3000,https://hopeaid.vercel.app"

    @property
    def cors_origins(self) -> List[str]:
        """Return CORS origins parsed from either JSON array or CSV string."""
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return []

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(origin).strip() for origin in parsed if str(origin).strip()]

        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    # ─── Storage (S3-compatible) ───────────────────────────────────────────────
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "hopeaid-uploads"
    S3_REGION: str = "ap-south-1"
    S3_PUBLIC_BASE_URL: Optional[str] = None

    # ─── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2048
    OPENAI_TEMPERATURE: float = 0.1

    # ─── Google APIs ──────────────────────────────────────────────────────────
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""

    # ─── Rate Limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10

    # ─── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"     # json | console

    # ─── Feature Flags ────────────────────────────────────────────────────────
    ENABLE_AI_FEATURES: bool = True
    ENABLE_OCR: bool = True
    ENABLE_TRANSLATION: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level convenience — import this everywhere
settings = get_settings()
