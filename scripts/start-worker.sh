#!/usr/bin/env sh
set -eu

LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"
QUEUE_LIST="${CELERY_QUEUES:-ocr,ai,reports,celery}"

python scripts/check_database_url.py

if [ -n "${CELERY_CONCURRENCY:-}" ]; then
  exec celery -A app.workers.celery_app worker \
    --loglevel="${LOG_LEVEL}" \
    -Q "${QUEUE_LIST}" \
    --concurrency="${CELERY_CONCURRENCY}"
fi

exec celery -A app.workers.celery_app worker \
  --loglevel="${LOG_LEVEL}" \
  -Q "${QUEUE_LIST}"
