#!/usr/bin/env python3
"""
Warn about DATABASE_URL values that commonly fail on Railway.

This stays non-blocking because Railway can optionally enable outbound IPv6.
The goal is to surface a precise fix in deploy logs before Alembic or the app
fails with a generic connection error.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit


RAILWAY_ENV_VARS = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_SERVICE_NAME",
    "RAILWAY_PUBLIC_DOMAIN",
)


def _running_on_railway() -> bool:
    return any(os.getenv(name) for name in RAILWAY_ENV_VARS)


def _database_hostname(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def _database_port(url: str) -> int | None:
    try:
        return urlsplit(url).port
    except ValueError:
        return None


def _is_direct_supabase_host(hostname: str) -> bool:
    return hostname.startswith("db.") and hostname.endswith(".supabase.co")


def _is_pooler_supabase_host(hostname: str) -> bool:
    return hostname.endswith(".pooler.supabase.com")


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or not _running_on_railway():
        return 0

    hostname = _database_hostname(database_url)
    if not hostname:
        return 0

    if _is_direct_supabase_host(hostname):
        print(
            f"[startup] WARNING: DATABASE_URL points to direct Supabase host '{hostname}'.",
            file=sys.stderr,
        )
        print(
            "[startup] On Railway, this only works when outbound IPv6 is enabled for the service.",
            file=sys.stderr,
        )
        print(
            "[startup] Preferred fix: use the Supabase session pooler URL on port 5432 instead.",
            file=sys.stderr,
        )
        print(
            "[startup] Expected host pattern: aws-0-<region>.pooler.supabase.com:5432",
            file=sys.stderr,
        )
        return 0

    if _is_pooler_supabase_host(hostname) and _database_port(database_url) == 6543:
        print(
            "[startup] NOTE: Supabase transaction pooler detected on port 6543.",
            file=sys.stderr,
        )
        print(
            "[startup] For long-lived SQLAlchemy connections and Alembic migrations, "
            "the session pooler on port 5432 is usually the safer choice.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
