# ─── HopeAid Backend — Dockerfile ────────────────────────────────────────────
# Multi-stage build: builder installs deps, final image is lean

FROM python:3.12-slim AS builder

WORKDIR /app

# System deps for psycopg2 and google-cloud libraries
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Final Stage ─────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r hopeaid && useradd -r -g hopeaid hopeaid
RUN chown -R hopeaid:hopeaid /app
USER hopeaid

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Production startup command
# Uses 4 workers with 2 threads each — tune WORKERS env var for your instance size
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--log-level", "info"]
