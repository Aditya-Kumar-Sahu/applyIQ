from __future__ import annotations

import contextlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.core.constants import (
    API_V1_PREFIX,
    APP_NAME,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_ENVIRONMENT,
    PROJECT_SLUG,
)


class SecretsManagerSettingsSource(PydanticBaseSettingsSource):
    """
    Custom settings source that loads secrets from a JSON file (local)
    or AWS Secrets Manager (production).
    """

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._cache: dict[str, Any] = {}
        self._loaded = False

    def _load_secrets(self) -> dict[str, Any]:
        if self._loaded:
            return self._cache

        secrets = {}
        provider = os.getenv("SECRETS_PROVIDER", "local").lower()

        # 1. AWS Secrets Manager Integration
        if provider == "aws":
            secrets.update(self._fetch_from_aws())

        # 2. Local Simulation: Look for .secrets.json in the project root
        # We check local even if provider is AWS as a developer convenience override
        secrets_file = Path(".secrets.json")
        if secrets_file.exists():
            with contextlib.suppress(Exception):
                secrets.update(json.loads(secrets_file.read_text()))

        self._cache = secrets
        self._loaded = True
        return secrets

    def _fetch_from_aws(self) -> dict[str, Any]:
        """
        Fetch secrets from AWS Secrets Manager.
        Expects AWS_REGION and SECRETS_NAME to be set in environment.
        """
        region_name = os.getenv("AWS_REGION", "us-east-1")
        secret_name = os.getenv("SECRETS_NAME", f"{PROJECT_SLUG}/{os.getenv('ENVIRONMENT', 'dev')}")

        try:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client("secretsmanager", region_name=region_name)
            response = client.get_secret_value(SecretId=secret_name)

            if "SecretString" in response:
                return json.loads(response["SecretString"])
            return {}
        except ImportError:
            # Only happens if boto3 is missing despite requirements
            return {}
        except Exception:
            # Log failure but allow fallback if necessary (or re-raise in strict prod)
            return {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._load_secrets()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    # Metadata
    app_name: str = APP_NAME
    project_slug: str = PROJECT_SLUG
    environment: str = DEFAULT_ENVIRONMENT
    release_version: str = "dev"

    # Server Config
    api_v1_prefix: str = API_V1_PREFIX
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_dir: str = "logs"
    log_file_name: str = "backend.log"
    log_file_max_bytes: int = 10 * 1024 * 1024
    log_file_backup_count: int = 5

    # --- SENSITIVE FIELDS ---
    database_url: SecretStr = Field(default=SecretStr("postgresql+asyncpg://applyiq:password@db:5432/applyiq"))
    redis_url: SecretStr = Field(default=SecretStr("redis://redis:6379/0"))
    celery_broker_url: SecretStr = Field(default=SecretStr("redis://redis:6379/1"))
    celery_result_backend: SecretStr = Field(default=SecretStr("redis://redis:6379/2"))
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    fernet_secret_key: SecretStr | None = None
    encryption_pepper: SecretStr | None = None
    apify_api_token: SecretStr | None = None
    serpapi_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    google_client_id: SecretStr | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None
    # --- END SENSITIVE FIELDS ---

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    access_cookie_name: str = "applyiq_access_token"
    refresh_cookie_name: str = "applyiq_refresh_token"
    auth_register_rate_limit: int = 5
    auth_login_rate_limit: int = 10
    auth_rate_window_seconds: int = 60
    secure_cookie_override: bool | None = None
    sentry_dsn_backend: str | None = None
    sentry_traces_sample_rate: float = 0.0
    sentry_profiles_sample_rate: float = 0.0

    # OpenTelemetry
    otel_service_name: str = PROJECT_SLUG
    otel_exporter_otlp_endpoint: str | None = None  # e.g. "http://collector:4317"
    otel_traces_sampler: str = "parentbased_always_on"
    otel_traces_sample_rate: float = 1.0

    enable_auto_apply: bool = True
    auto_apply_demo_mode: bool = False
    playwright_enabled: bool = True
    auto_apply_headless: bool = True
    auto_apply_artifact_root: str = "artifacts"
    max_auto_apply_per_run: int = 20
    pipeline_checkpoint_ttl_seconds: int = 24 * 60 * 60
    pipeline_start_rate_limit: int = 6
    pipeline_start_rate_window_seconds: int = 60 * 60
    pipeline_task_mode: str = "celery"
    max_resume_upload_bytes: int = 5 * 1024 * 1024
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"
    gmail_oauth_scope: str = "https://www.googleapis.com/auth/gmail.readonly"
    gmail_poll_max_messages: int = 25

    # Provider Config
    secrets_provider: str = "local"  # local, aws

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            SecretsManagerSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

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
        jwt_key = self.jwt_secret_key.get_secret_value() if self.jwt_secret_key else None
        fernet_key = self.fernet_secret_key.get_secret_value() if self.fernet_secret_key else None
        pepper = self.encryption_pepper.get_secret_value() if self.encryption_pepper else None

        missing_secrets = [
            name
            for name, value in (
                ("JWT_SECRET_KEY", jwt_key),
                ("FERNET_SECRET_KEY", fernet_key),
                ("ENCRYPTION_PEPPER", pepper),
            )
            if value is None or not str(value).strip()
        ]

        if missing_secrets:
            raise RuntimeError(
                f"Missing required secrets: {', '.join(missing_secrets)}. "
                "Populate them in the Secret Manager or environment."
            )

        if not self.is_non_production:
            if not self.secure_cookies:
                raise RuntimeError("Secure cookies must be enabled outside non-production environments")

            # HARDENING: In production, we MUST NOT use the local provider
            if self.secrets_provider == "local":
                raise RuntimeError(
                    "Security Violation: Local secrets provider detected in production environment. "
                    "SECRETS_PROVIDER must be set to 'aws' or another managed service."
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
