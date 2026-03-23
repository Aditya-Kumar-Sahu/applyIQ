from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import API_V1_PREFIX, APP_NAME, DEFAULT_CORS_ORIGINS, DEFAULT_ENVIRONMENT, PROJECT_SLUG


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = APP_NAME
    project_slug: str = PROJECT_SLUG
    environment: str = DEFAULT_ENVIRONMENT
    api_v1_prefix: str = API_V1_PREFIX
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())
    database_url: str = "postgresql+asyncpg://applyiq:password@db:5432/applyiq"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    access_cookie_name: str = "applyiq_access_token"
    refresh_cookie_name: str = "applyiq_refresh_token"
    fernet_secret_key: str = "wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID="
    encryption_pepper: str = "applyiq-pepper"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
