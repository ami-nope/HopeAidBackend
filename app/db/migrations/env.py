"""
app/db/migrations/env.py — Alembic environment configuration (fully synchronous).

Loads DATABASE_URL from settings and runs migrations against PostgreSQL.
Supports offline mode (generates SQL script) and online mode (live migration).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base

# Import all models so Alembic detects all table definitions in Base.metadata.
# The assignment to _ is intentional — it prevents pyflakes from flagging this
# as an unused import while still executing the side-effect of registering models.
import app.models as _models
_ = _models.__all__


# Alembic Config object — gives access to values in alembic.ini
config = context.config

# Override the DB URL with our settings value (from .env)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Setup Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata object that Alembic inspects to plan migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This generates a SQL script instead of connecting to the database.
    Useful for reviewing changes before applying them.

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the real database.

    Uses a NullPool so each migration gets a fresh connection
    (important for Alembic's transaction management).

    Usage: alembic upgrade head
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,   # No connection pooling for migrations
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


# Alembic calls either offline or online based on the --sql flag
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
