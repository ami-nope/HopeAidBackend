#!/usr/bin/env sh
set -eu

LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"

exec celery -A app.workers.celery_app beat --loglevel="${LOG_LEVEL}"
