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
    
    # DB & Third-Party APIs
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/reflexion"
    GEMINI_API_KEY: str = ""
    
    # Git Storage
    LOCAL_WORKSPACE_DIR: str = os.path.join(os.path.expanduser("~"), ".reflexion", "workspaces")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
