from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


# ---------------------------------------------------------------------------
# Lifespan – runs once on startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Startup: import models so SQLModel metadata is fully populated.
    This is required before Alembic autogenerate or init_db() can work.
    """
    import app.models  # noqa: F401 – side-effect: register table metadata
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Configure CORS for Frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://reflexion.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Reflexion AI Pull Request Agent API"}


@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check():
    """Basic liveness probe – does not touch the database."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "api_version": "v1",
    }


@app.get(f"{settings.API_V1_STR}/health/db", tags=["Health"])
def health_check_db():
    """
    Readiness probe – verifies the database connection is alive.
    Returns the PostgreSQL server version on success.
    """
    from app.database import verify_connection

    try:
        result = verify_connection()
        return {
            "status": "healthy",
            "project": settings.PROJECT_NAME,
            "database": result,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "project": settings.PROJECT_NAME,
            "database": {"status": "disconnected", "error": str(exc)},
        }
