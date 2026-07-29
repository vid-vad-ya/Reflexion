import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Reflexion"
    API_V1_STR: str = "/api/v1"

    # Security & Auth
    SECRET_KEY: str = "supersecretkeychangeinproduction"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    ENCRYPTION_KEY: str = ""

    # Database
    # Local dev:  postgresql://postgres:postgres@localhost:5432/reflexion
    # Neon (session pooler):      postgresql://user:pass@ep-xxx.neon.tech:5432/neondb?sslmode=require
    # Neon (transaction pooler):  postgresql://user:pass@ep-xxx.neon.tech:6432/neondb?sslmode=require
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/reflexion"
    # Set DB_ECHO=true in .env to print every SQL statement (dev only)
    DB_ECHO: bool = False

    # Third-party APIs
    # LLM Configuration
    LLM_PROVIDER: str = "groq"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    

    # Git Storage
    LOCAL_WORKSPACE_DIR: str = os.path.join(
        os.path.expanduser("~"), ".reflexion", "workspaces"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

