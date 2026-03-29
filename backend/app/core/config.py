from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import API_V1_PREFIX, APP_NAME, DEFAULT_CORS_ORIGINS, DEFAULT_ENVIRONMENT, PROJECT_SLUG


_DEFAULT_JWT_SECRET = "change-me-in-production"
_DEFAULT_FERNET_SECRET = "wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID="
_DEFAULT_ENCRYPTION_PEPPER = "applyiq-pepper"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = APP_NAME
    project_slug: str = PROJECT_SLUG
    environment: str = DEFAULT_ENVIRONMENT
    api_v1_prefix: str = API_V1_PREFIX
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    release_version: str = "dev"
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())
    database_url: str = "postgresql+asyncpg://applyiq:password@db:5432/applyiq"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    access_cookie_name: str = "applyiq_access_token"
    refresh_cookie_name: str = "applyiq_refresh_token"
    fernet_secret_key: str = _DEFAULT_FERNET_SECRET
    encryption_pepper: str = _DEFAULT_ENCRYPTION_PEPPER
    secure_cookie_override: bool | None = None
    sentry_dsn_backend: str | None = None
    sentry_traces_sample_rate: float = 0.0
    sentry_profiles_sample_rate: float = 0.0
    enable_auto_apply: bool = True
    max_auto_apply_per_run: int = 20
    pipeline_checkpoint_ttl_seconds: int = 24 * 60 * 60
    pipeline_start_rate_limit: int = 6
    pipeline_start_rate_window_seconds: int = 60 * 60
    pipeline_task_mode: str = "celery"
    max_resume_upload_bytes: int = 5 * 1024 * 1024

    @property
    def is_non_production(self) -> bool:
        return self.environment.lower() in {"development", "test", "local"}

    @property
    def secure_cookies(self) -> bool:
        if self.secure_cookie_override is not None:
            return self.secure_cookie_override
        return not self.is_non_production

    @property
    def execute_pipeline_inline(self) -> bool:
        if self.environment.lower() == "test":
            return True
        return self.pipeline_task_mode.lower() == "inline"

    def validate_security_contract(self) -> None:
        if self.is_non_production:
            return

        if self.jwt_secret_key == _DEFAULT_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be overridden outside non-production environments")
        if self.fernet_secret_key == _DEFAULT_FERNET_SECRET:
            raise ValueError("FERNET_SECRET_KEY must be overridden outside non-production environments")
        if self.encryption_pepper in {_DEFAULT_ENCRYPTION_PEPPER, "change-me-in-production"}:
            raise ValueError("ENCRYPTION_PEPPER must be overridden outside non-production environments")
        if not self.secure_cookies:
            raise ValueError("Secure cookies must be enabled outside non-production environments")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
