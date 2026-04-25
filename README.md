# HopeAid Backend

Production-ready REST API backend for the HopeAid humanitarian aid management platform.

**Stack**: FastAPI · PostgreSQL · Redis + Celery · SQLAlchemy 2.0 · Pydantic v2 · OpenAI · Google Vision/Translate · S3

---

## Quick Start (Local with Docker)

```bash
# 1. Clone and enter directory
git clone <repo> hopeaid-backend
cd hopeaid-backend

# 2. Copy and configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY, OPENAI_API_KEY, and at minimum leave DB/Redis as-is for Docker

# 3. Start all services
docker compose up --build -d

# 4. Run migrations
docker compose exec api alembic upgrade head

# 5. Load seed data
docker compose exec api python -m app.db.seed

# 6. Visit docs
open http://localhost:8000/docs
```

**Demo credentials** (after seeding):
- Super Admin: `admin@hopeaid.platform` / `Admin@1234`
- Org Manager: `manager@hopeaid-demo.org` / `Manager@1234`

---

## Local Development (Without Docker)

### Prerequisites
- Python 3.12+
- PostgreSQL 14+ running locally
- Redis 6+ running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your local DB/Redis URLs

# Run migrations
alembic upgrade head

# Seed data
python -m app.db.seed

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info -Q ocr,ai,reports,celery

# Start Celery beat scheduler (separate terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

---

## Running Tests

```bash
# Install test extras
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite

# Run all tests with coverage
pytest

# Run specific test file
pytest app/tests/test_auth.py -v

# Run only unit tests (no DB)
pytest app/tests/test_allocation.py app/tests/test_duplicate.py -v
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | JWT signing key — generate with `openssl rand -hex 32` |
| `DATABASE_URL` | ✅ | Sync PostgreSQL URL (`postgresql+psycopg2://...`) |
| `REDIS_URL` | ✅ | Redis connection URL |
| `CELERY_BROKER_URL` | ✅ | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND` | ✅ | Redis URL for Celery results |
| `CORS_ORIGINS` | ✅ | Comma-separated origins or JSON array string |
| `S3_ACCESS_KEY_ID` | ✅ | S3/storage access key |
| `S3_SECRET_ACCESS_KEY` | ✅ | S3/storage secret |
| `S3_BUCKET_NAME` | ✅ | S3 bucket for uploads |
| `OPENAI_API_KEY` | ⬜ | OpenAI API key (AI features disabled if missing) |
| `GOOGLE_APPLICATION_CREDENTIALS` | ⬜ | Google service account JSON path (OCR/translate) |
| `S3_ENDPOINT_URL` | ⬜ | For non-AWS S3 (Supabase, MinIO, R2) |
| `ENVIRONMENT` | ⬜ | `development` / `staging` / `production` |

---

## Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Check current migration status
alembic current
```

---

## Railway Deployment

1. **Create a Railway project** and add a PostgreSQL plugin
2. **Add a Redis plugin**
3. **Set environment variables** in Railway dashboard (copy from `.env.example`)
   - If you are using Supabase instead of the Railway PostgreSQL plugin, set `DATABASE_URL` manually to the Supabase session pooler URL on port `5432`.
   - Do not use the direct `db.<project-ref>.supabase.co` host on Railway unless outbound IPv6 is enabled for that service.
   - In `Settings -> Networking -> Public Networking`, make sure the service domain target port matches the app's listen port. For this repo on Railway, that should be the injected `PORT` value, which is typically `8080`.
4. **Use included config files**:
  - `railway.json` (deploy metadata)
  - `scripts/start-web.sh` (migrations + API startup)
5. **Set the web service start command**:
   ```
  sh scripts/start-web.sh
   ```
6. **Deploy Celery worker** as a separate Railway service with command:
   ```
  sh scripts/start-worker.sh
   ```
7. **Deploy Celery beat** as another Railway service:
   ```
  sh scripts/start-beat.sh
   ```

### Railway Environment Variables
Railway auto-injects `DATABASE_URL` and `REDIS_URL` from plugins.

- `DATABASE_URL` values with `postgres://` or `postgresql://` are auto-normalized to sync psycopg2 in app config.
- Railway PostgreSQL plugin users can keep the auto-injected `DATABASE_URL`.
- Supabase users should override `DATABASE_URL` with the Supabase session pooler URL from Supabase Dashboard -> Connect.
- Use the session pooler on port `5432` for this app's FastAPI + SQLAlchemy + Alembic workload.
- The direct Supabase host `db.<project-ref>.supabase.co:5432` depends on IPv6. Railway outbound IPv6 is disabled by default, so enable it per service if you want to keep using the direct host instead of the pooler.
- Keep `CORS_ORIGINS` as CSV (`https://a.com,https://b.com`) or JSON array string (`["https://a.com","https://b.com"]`).

---

## API Overview

Base URL: `https://your-app.railway.app/api/v1`

### Authentication
```bash
# Register
curl -X POST /api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"organization_id": "...", "name": "John", "email": "john@org.com", "password": "Pass@1234"}'

# Login
curl -X POST /api/v1/auth/login \
  -d '{"email": "john@org.com", "password": "Pass@1234"}'

# Use token
curl -H "Authorization: Bearer <access_token>" /api/v1/auth/me
```

### Create a Case
```bash
curl -X POST /api/v1/cases \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Food and water shortage — 25 families",
    "category": "food",
    "urgency_level": "critical",
    "disaster_type": "flood",
    "number_of_people_affected": 100,
    "location_name": "Relief Camp B, Chennai"
  }'
```

### Get Allocation Recommendations
```bash
curl -X POST /api/v1/allocation/recommend?case_id=<case_uuid> \
  -H "Authorization: Bearer <token>"
```

### Upload and OCR a Document
```bash
curl -X POST /api/v1/uploads \
  -H "Authorization: Bearer <token>" \
  -F "file=@intake_form.jpg" \
  -F "source=case_form" \
  -F "auto_process=true"
```

### Translate Case Summary
```bash
curl -X POST /api/v1/ai/translate \
  -H "Authorization: Bearer <token>" \
  -d '{"text": "Family needs urgent food", "target_language": "hi"}'
```

### Export Cases as CSV
```bash
curl -H "Authorization: Bearer <token>" /api/v1/exports/cases.csv -o cases.csv
```

---

## Architecture

```
Frontend (Next.js/Vercel)
        ↓ HTTPS
FastAPI API (/api/v1)
  ├── Auth (JWT + Redis refresh tokens)
  ├── Cases (central entity, status machine)
  ├── Households & Persons
  ├── Volunteers & Availability
  ├── Inventory & Stock movements
  ├── Uploads → OCR → AI extraction pipeline
  ├── Allocation engine (rule-based + AI explanations)
  ├── Reports & CSV/PDF exports
  └── Admin (audit logs, forms, settings)
        ↓
PostgreSQL (primary data)
Redis (cache + Celery queue)
Celery Workers (OCR, AI, reports)
Celery Beat (daily summaries, alerts)
S3-compatible storage (uploads)
Google Vision (OCR)
OpenAI (extraction, explanations, reports)
Google Translate (multilingual)
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                # FastAPI app factory
│   ├── core/                  # Config, security, logging, constants
│   ├── db/                    # Session, base, migrations, seed
│   ├── models/                # 13 SQLAlchemy ORM models
│   ├── schemas/               # 14 Pydantic v2 schema modules
│   ├── api/v1/routes/         # 12 route modules (68 endpoints)
│   ├── services/              # Business logic layer
│   ├── integrations/          # OCR, LLM, translation, storage
│   ├── workers/               # Celery tasks + beat schedule
│   ├── utils/                 # Risk scorer, duplicate detector, pagination
│   └── tests/                 # 9 test modules
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Key Design Decisions

1. **SQLAlchemy 2.0 sync** — not SQLModel; mature and predictable for this service architecture
2. **Repository-free for v1** — services call SQLAlchemy directly; add repos if needed for testing
3. **Organization scoping on every query** — multi-tenancy at Python layer, not DB row-level security
4. **AI is fully optional** — set `ENABLE_AI_FEATURES=false` and system works without OpenAI
5. **Celery over background tasks** — needed for retry logic, monitoring via Flower, and task chains
6. **Risk score is deterministic** — no AI involvement; fully rule-based for auditability
7. **Allocation score is transparent** — structured breakdown returned in every recommendation

---

## License

MIT — see LICENSE file.
