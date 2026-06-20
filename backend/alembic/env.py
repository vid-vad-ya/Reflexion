"""
alembic/env.py – Alembic migration environment.

This file is executed every time Alembic runs (upgrade, downgrade,
autogenerate, etc.).  It configures:

  1. The SQLAlchemy engine URL from settings.DATABASE_URL (overriding
     whatever is in alembic.ini).
  2. The target metadata from SQLModel so that --autogenerate can detect
     model changes.
  3. Both "offline" (SQL script) and "online" (live connection) migration
     modes.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Add backend project root to Python's import search path
# ---------------------------------------------------------------------------
# This guarantees that the 'app' package is discoverable regardless of how
# or where the alembic command is invoked (e.g. running 'alembic current'
# from the 'backend' directory).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---------------------------------------------------------------------------
# Import application settings & models
# ---------------------------------------------------------------------------
# This import chain causes all SQLModel table classes to register their
# metadata, which is required for autogenerate to detect schema diffs.

from app.core.config import settings  # noqa: E402
import app.models                     # noqa: F401, E402


from sqlmodel import SQLModel

# ---------------------------------------------------------------------------
# Alembic Config object – provides access to alembic.ini values.
# ---------------------------------------------------------------------------
config = context.config

# Override the URL from alembic.ini with the one from our app settings.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from the [loggers] section of alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# MetaData target for autogenerate support
# ---------------------------------------------------------------------------
target_metadata = SQLModel.metadata


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL without a live database connection)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This emits SQL statements to stdout (or a file) rather than executing
    them against a live database.  Useful for generating migration scripts
    that a DBA will review before applying.

    Calls to context.execute() here emit the given string to the script
    output.
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


# ---------------------------------------------------------------------------
# Online migrations (execute against a live database connection)
# ---------------------------------------------------------------------------

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an Engine from alembic.ini config, establishes a connection,
    and runs migrations inside a transaction.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # always use NullPool for migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entrypoint – Alembic calls this automatically.
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
