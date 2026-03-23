from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


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


def test_versioned_meta_endpoint_returns_standard_envelope() -> None:
    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(health_reporter=healthy_reporter)
    client = TestClient(app)

    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"service": "applyiq", "environment": "development"},
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
