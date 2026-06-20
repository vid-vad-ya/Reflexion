"""
database.py – SQLModel / SQLAlchemy engine, session factory, and helpers.

This module is the single source of truth for database connectivity.
All other modules that need a DB session import `get_session` from here.

Architecture:
    • create_engine()  – creates the global SQLAlchemy engine with connection
                         pooling tuned for Neon serverless Postgres.
    • SQLModel.metadata – shared MetaData; used by Alembic for autogenerate.
    • get_session()    – FastAPI dependency that opens, yields, and closes
                         a session per HTTP request (request-scoped UoW).
    • init_db()        – convenience helper for local dev / test: creates all
                         tables directly from metadata (no Alembic needed).

Neon-specific notes:
    • Neon uses PgBouncer for connection pooling; keep pool_size small and
      enable pool_pre_ping so stale connections are detected automatically.
    • pool_recycle ensures long-lived connections are periodically refreshed
      (Neon drops idle connections after 5 minutes by default).
    • For the session-mode PgBouncer URL (port 5432) set
      pool_size=5, max_overflow=10.
    • For the transaction-mode PgBouncer URL (port 6432) you MUST add
      ?options=endpoint%3D<endpoint-id> to the URL and use NullPool:
          from sqlalchemy.pool import NullPool
          engine = create_engine(url, poolclass=NullPool)
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import event, text
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# Detect whether we are using the Neon transaction-mode pooler (port 6432).
# When True, SQLAlchemy must NOT maintain its own connection pool because
# PgBouncer already manages connections at the transaction boundary.
_USE_NULL_POOL: bool = ":6432" in settings.DATABASE_URL

engine = create_engine(
    settings.DATABASE_URL,
    # echo=True prints every SQL statement – very useful for debugging,
    # but should be False (or filtered) in production.
    echo=settings.DB_ECHO,
    # NullPool: open/close a real connection for every session, which is
    # required by Neon's transaction-mode pooler.
    # Regular pool: maintain persistent connections (session-mode pooler or
    # direct Postgres).
    poolclass=NullPool if _USE_NULL_POOL else None,
    # pool_size / max_overflow are ignored when NullPool is active.
    pool_size=5         if not _USE_NULL_POOL else None,        # type: ignore[arg-type]
    max_overflow=10     if not _USE_NULL_POOL else None,        # type: ignore[arg-type]
    # Refresh connections older than 4 minutes (< Neon's 5-min idle timeout).
    pool_recycle=240    if not _USE_NULL_POOL else None,        # type: ignore[arg-type]
    # Emit a cheap SELECT 1 before each checkout to detect broken connections.
    pool_pre_ping=True  if not _USE_NULL_POOL else None,        # type: ignore[arg-type]
    # Let psycopg2 resolve SRV / hostname changes without caching (Neon SNI).
    connect_args={"sslmode": "require"} if "neon.tech" in settings.DATABASE_URL else {},
)


# ---------------------------------------------------------------------------
# FastAPI dependency – request-scoped session
# ---------------------------------------------------------------------------

def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency.  Yields one SQLModel Session per HTTP request and
    guarantees it is closed (and rolled back on error) when the request ends.

    Usage in a router:
        from fastapi import Depends
        from app.database import get_session

        @router.get("/items")
        def list_items(session: Session = Depends(get_session)):
            return session.exec(select(Item)).all()
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# ---------------------------------------------------------------------------
# Context-manager variant (useful in background tasks / scripts)
# ---------------------------------------------------------------------------

@contextmanager
def get_session_ctx() -> Generator[Session, None, None]:
    """
    Context-manager version of get_session for use outside FastAPI's
    dependency-injection system (e.g. Celery tasks, CLI scripts).

    Usage:
        from app.database import get_session_ctx

        with get_session_ctx() as session:
            user = session.get(User, user_id)
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# ---------------------------------------------------------------------------
# Dev / test helper
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in SQLModel metadata.

    ⚠️  For local development and CI only.
    In production use Alembic migrations (`alembic upgrade head`) so that
    schema changes are applied incrementally and tracked.
    """
    # Import models so their metadata is registered before create_all().
    import app.models  # noqa: F401  – side-effect: registers table metadata

    SQLModel.metadata.create_all(engine)


def verify_connection() -> dict:
    """
    Verify that the engine can reach the database server.

    Returns a dict with 'status' and 'version' keys so the result can be
    surfaced via an API health endpoint.

    Raises:
        sqlalchemy.exc.OperationalError  if the connection fails.
    """
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version()")).fetchone()
        return {
            "status": "connected",
            "version": row[0] if row else "unknown",
        }
