"""
test_db.py — Quick synchronous database connectivity test.

Run with:  py test_db.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Auto-fix common wrong prefixes to psycopg2 sync driver
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


def test_connection():
    if not DATABASE_URL:
        print("[ERROR] DATABASE_URL not set in .env")
        return

    print(f"[*] Connecting to: {DATABASE_URL[:60]}...")

    try:
        engine = create_engine(DATABASE_URL)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user, version()"))
            row = result.fetchone()
            print("[OK] Connected to database successfully!")
            print(f"   Database   : {row[0]}")
            print(f"   User       : {row[1]}")
            print(f"   PG Version : {row[2][:60]}")

    except Exception as e:
        print("[FAILED] Connection failed:")
        print(f"   {type(e).__name__}: {e}")
        print()
        print("Common fixes:")
        print("  * Make sure DATABASE_URL uses postgresql+psycopg2:// prefix")
        print("  * Make sure psycopg2-binary is installed: pip install psycopg2-binary")
        print("  * Check your password for special characters needing URL encoding")
        print("  * Verify the Supabase project is active (pauses after inactivity)")


if __name__ == "__main__":
    test_connection()