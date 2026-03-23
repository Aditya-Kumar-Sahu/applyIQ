from __future__ import annotations

from app.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.app_name == "ApplyIQ API"
    assert settings.environment == "development"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.project_slug == "applyiq"
