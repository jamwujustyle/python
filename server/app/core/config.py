from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Users API"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./sql_app.db"

    # JWT Security Settings
    # In production, these must be overridden with strong keys
    JWT_SECRET_KEY: str = (
        "SUPER_SECRET_KEY_FOR_LOCAL_DEV_CHANGE_THIS_IN_PROD_1234567890"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis and Celery Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery Broker/Backend
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Returns a cached Settings instance. Use app.dependency_overrides[get_settings] in tests."""
    return Settings()


# Module-level shorthand — same cached instance, compatible with all existing imports
settings = get_settings()
