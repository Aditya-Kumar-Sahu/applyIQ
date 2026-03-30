from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None, _env_prefix="__applyiq_test__")

    assert settings.app_name == "ApplyIQ API"
    assert settings.environment == "development"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.project_slug == "applyiq"
    assert settings.release_version == "dev"
    assert settings.log_to_file is True
    assert settings.log_dir == "logs"
    assert settings.log_file_name == "backend.log"
    assert settings.log_file_max_bytes == 10 * 1024 * 1024
    assert settings.log_file_backup_count == 5
    assert settings.enable_auto_apply is True
    assert settings.max_auto_apply_per_run == 20
    assert settings.sentry_dsn_backend is None
    assert settings.jwt_secret_key is None
    assert settings.fernet_secret_key is None
    assert settings.encryption_pepper is None
    assert settings.gemini_api_key is None
    assert settings.gemini_chat_model == "gemini-2.0-flash"
    assert settings.gemini_embedding_model == "text-embedding-004"


def test_create_app_requires_secrets_before_startup() -> None:
    settings = Settings(
        _env_file=None,
        _env_prefix="__applyiq_test__",
        environment="test",
        jwt_secret_key=None,
        fernet_secret_key=None,
        encryption_pepper=None,
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=settings, health_reporter=healthy_reporter)

    with pytest.raises(RuntimeError, match="Missing required secrets"):
        with TestClient(app):
            pass
