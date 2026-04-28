#!/usr/bin/env sh
set -eu

PORT="${PORT:-8080}"
WORKERS="${WEB_CONCURRENCY:-2}"
LOG_LEVEL="${UVICORN_LOG_LEVEL:-info}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
MIGRATIONS_BLOCK_STARTUP="${MIGRATIONS_BLOCK_STARTUP:-false}"
MIGRATION_STARTUP_TIMEOUT_SECONDS="${MIGRATION_STARTUP_TIMEOUT_SECONDS:-45}"

python scripts/check_database_url.py

if [ "${RUN_MIGRATIONS}" = "true" ]; then
  echo "[startup] Running database migrations..."
  if command -v timeout >/dev/null 2>&1; then
    if ! timeout "${MIGRATION_STARTUP_TIMEOUT_SECONDS}" alembic upgrade head; then
      echo "[startup] WARNING: migrations failed or timed out after ${MIGRATION_STARTUP_TIMEOUT_SECONDS}s."
      if [ "${MIGRATIONS_BLOCK_STARTUP}" = "true" ]; then
        exit 1
      fi
      echo "[startup] Continuing startup without blocking on migrations."
    fi
  else
    if ! alembic upgrade head; then
      echo "[startup] WARNING: migrations failed."
      if [ "${MIGRATIONS_BLOCK_STARTUP}" = "true" ]; then
        exit 1
      fi
      echo "[startup] Continuing startup without blocking on migrations."
    fi
  fi
fi

echo "[startup] Starting API on port ${PORT} with ${WORKERS} workers..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --loop uvloop \
  --log-level "${LOG_LEVEL}"
