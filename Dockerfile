# ─── HopeAid Backend — Dockerfile ────────────────────────────────────────────
# Multi-stage build: builder installs deps, final image is lean.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

# Build deps for psycopg2 and crypto wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
  gcc \
  libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Final Stage ─────────────────────────────────────────────────────────────

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime deps: libpq5 for psycopg2, curl for health checks.
RUN apt-get update && apt-get install -y --no-install-recommends \
  libpq5 \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder.
COPY --from=builder /install /usr/local

# Copy application code.
COPY . .

# Create non-root user for security.
RUN groupadd -r hopeaid && useradd -r -g hopeaid hopeaid
RUN chmod +x scripts/*.sh
RUN chown -R hopeaid:hopeaid /app
USER hopeaid

# Expose API port (Railway injects PORT at runtime).
EXPOSE 8000

# Health check targets Railway-ready /health endpoint.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1

# Production startup command.
CMD ["sh", "scripts/start-web.sh"]
