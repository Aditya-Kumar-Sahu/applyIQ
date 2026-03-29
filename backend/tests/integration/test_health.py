from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _production_like_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "environment": "staging",
        "jwt_secret_key": "test-jwt-secret",
        "fernet_secret_key": "test-fernet-secret",
        "encryption_pepper": "test-pepper",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _patch_core_dependency_pings(monkeypatch, *, db_ok: bool, redis_ok: bool) -> None:
    async def fake_db_ping(self) -> bool:
        return db_ok

    async def fake_redis_ping(self) -> bool:
        return redis_ok

    monkeypatch.setattr("app.main.DatabaseManager.ping", fake_db_ping)
    monkeypatch.setattr("app.main.RedisManager.ping", fake_redis_ping)


def test_health_endpoint_reports_all_dependencies_healthy() -> None:
    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(health_reporter=healthy_reporter)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "up", "redis": "up"}


def test_health_endpoint_returns_503_when_health_reporter_crashes() -> None:
    async def crashing_reporter() -> dict[str, str]:
        raise RuntimeError("simulated dependency failure")

    app = create_app(health_reporter=crashing_reporter)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "down", "redis": "down"}


def test_health_endpoint_includes_api_statuses_in_production_like_environment(monkeypatch) -> None:
    _patch_core_dependency_pings(monkeypatch, db_ok=True, redis_ok=True)

    async def fake_external_statuses(_: Settings) -> dict[str, str]:
        return {
            "apify": "up",
            "serpapi": "up",
            "remotive": "up",
            "indeed": "fixture",
            "wellfound": "fixture",
            "ai_provider": "not_configured",
        }

    monkeypatch.setattr("app.main._build_external_api_statuses", fake_external_statuses)

    app = create_app(settings=_production_like_settings())
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "up",
        "redis": "up",
        "apify": "up",
        "serpapi": "up",
        "remotive": "up",
        "indeed": "fixture",
        "wellfound": "fixture",
        "ai_provider": "not_configured",
    }


def test_health_endpoint_returns_503_when_required_external_api_is_down(monkeypatch) -> None:
    _patch_core_dependency_pings(monkeypatch, db_ok=True, redis_ok=True)

    async def fake_external_statuses(_: Settings) -> dict[str, str]:
        return {
            "apify": "up",
            "serpapi": "up",
            "remotive": "down",
            "indeed": "fixture",
            "wellfound": "fixture",
            "ai_provider": "not_configured",
        }

    monkeypatch.setattr("app.main._build_external_api_statuses", fake_external_statuses)

    app = create_app(settings=_production_like_settings())
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["remotive"] == "down"


def test_health_endpoint_returns_503_when_required_credentials_are_missing(monkeypatch) -> None:
    _patch_core_dependency_pings(monkeypatch, db_ok=True, redis_ok=True)

    async def fake_remotive_probe() -> str:
        return "up"

    monkeypatch.setattr("app.main._probe_remotive", fake_remotive_probe)

    app = create_app(settings=_production_like_settings(apify_api_token=None, serpapi_api_key=None))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["apify"] == "not_configured"
    assert response.json()["serpapi"] == "not_configured"


def test_health_endpoint_skips_external_api_checks_in_non_production(monkeypatch) -> None:
    _patch_core_dependency_pings(monkeypatch, db_ok=True, redis_ok=True)

    async def fail_if_called(_: Settings) -> dict[str, str]:
        raise AssertionError("external API checks should not run in non-production")

    monkeypatch.setattr("app.main._build_external_api_statuses", fail_if_called)

    app = create_app(settings=Settings(environment="development"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "up", "redis": "up"}


def test_versioned_meta_endpoint_returns_standard_envelope() -> None:
    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=Settings(environment="development"), health_reporter=healthy_reporter)
    client = TestClient(app)
    expected_environment = Settings().environment

    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"service": "applyiq", "environment": expected_environment},
        "error": None,
    }


def test_cors_preflight_allows_local_frontend_origin() -> None:
    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(health_reporter=healthy_reporter)
    client = TestClient(app)

    response = client.options(
        "/api/v1/meta",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
