#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"
LOG_LEVEL="${UVICORN_LOG_LEVEL:-info}"

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[startup] Running database migrations..."
  alembic upgrade head
fi

echo "[startup] Starting API on port ${PORT} with ${WORKERS} workers..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --loop uvloop \
  --log-level "${LOG_LEVEL}"
