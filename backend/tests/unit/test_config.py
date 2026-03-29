from __future__ import annotations

from app.core.config import Settings


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
    assert settings.gemini_api_key is None
    assert settings.gemini_chat_model == "gemini-2.0-flash"
    assert settings.gemini_embedding_model == "text-embedding-004"
