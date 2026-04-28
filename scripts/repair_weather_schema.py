"""Repair a partially-applied weather intelligence schema.

This script is idempotent and is intended for production recovery when:
- ORM startup `create_all()` created new tables
- existing tables were not altered
- Alembic's version table was left empty
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings


REPAIR_SQL = [
    """
    DO $$
    BEGIN
        CREATE TYPE geocode_status_enum AS ENUM (
            'not_requested',
            'pending',
            'resolved',
            'failed',
            'manual_review'
        );
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END $$;
    """,
    """
    DO $$
    BEGIN
        CREATE TYPE weather_risk_band_enum AS ENUM (
            'clear',
            'watch',
            'elevated',
            'severe'
        );
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END $$;
    """,
    """
    DO $$
    BEGIN
        CREATE TYPE hazard_assessment_risk_band_enum AS ENUM (
            'clear',
            'watch',
            'elevated',
            'severe'
        );
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END $$;
    """,
    "ALTER TYPE alert_type_enum ADD VALUE IF NOT EXISTS 'weather_risk';",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS geocode_status geocode_status_enum;",
    "UPDATE cases SET geocode_status = 'not_requested' WHERE geocode_status IS NULL;",
    "ALTER TABLE cases ALTER COLUMN geocode_status SET DEFAULT 'not_requested';",
    "ALTER TABLE cases ALTER COLUMN geocode_status SET NOT NULL;",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS geocode_provider VARCHAR(50);",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS geocode_confidence NUMERIC(5, 2);",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS district VARCHAR(150);",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS state VARCHAR(150);",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS weather_risk_band weather_risk_band_enum;",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_weather_checked_at TIMESTAMPTZ;",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS next_weather_check_at TIMESTAMPTZ;",
    "CREATE INDEX IF NOT EXISTS ix_cases_geocode_status ON cases (geocode_status);",
    "CREATE INDEX IF NOT EXISTS ix_cases_district ON cases (district);",
    "CREATE INDEX IF NOT EXISTS ix_cases_state ON cases (state);",
    "CREATE INDEX IF NOT EXISTS ix_cases_weather_risk_band ON cases (weather_risk_band);",
    "CREATE INDEX IF NOT EXISTS ix_cases_next_weather_check_at ON cases (next_weather_check_at);",
    """
    CREATE TABLE IF NOT EXISTS alembic_version (
        version_num VARCHAR(32) NOT NULL
    );
    """,
    "DELETE FROM alembic_version;",
    "INSERT INTO alembic_version (version_num) VALUES ('202604280600');",
]


VERIFY_SQL = {
    "case_columns": """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cases'
          AND column_name IN (
              'geocode_status',
              'geocode_provider',
              'geocode_confidence',
              'district',
              'state',
              'weather_risk_band',
              'last_weather_checked_at',
              'next_weather_check_at'
          )
        ORDER BY column_name;
    """,
    "alert_enum": """
        SELECT enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'alert_type_enum'
        ORDER BY e.enumsortorder;
    """,
    "alembic_version": "SELECT version_num FROM alembic_version;",
}


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)

    with engine.begin() as conn:
        for statement in REPAIR_SQL:
            conn.execute(text(statement))

        print("Repair applied.")
        for label, query in VERIFY_SQL.items():
            rows = conn.execute(text(query)).fetchall()
            print(f"{label}: {rows}")


if __name__ == "__main__":
    main()
