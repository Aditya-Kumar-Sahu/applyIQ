from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.auto_apply.ats.base import BrowserApplyResult
from app.api.v1.routes import pipeline as pipeline_routes
from app.api.v1.routes import scrape as scrape_routes
from app.services.auto_apply_service import AutoApplyService
from app.services.scrape_service import ScrapeService as RealScrapeService
from tests.helpers.scrape_fixtures import build_fixture_scrapers


@pytest.fixture(autouse=True)
def _patch_integration_scrape_services(monkeypatch, request):
    path = str(getattr(request.node, "path", getattr(request.node, "fspath", ""))).replace("\\", "/")
    if "/tests/integration/" not in path:
        yield
        return

    def _factory(*, embedding_service, deduplicator, settings=None, scrapers=None):
        return RealScrapeService(
            embedding_service=embedding_service,
            deduplicator=deduplicator,
            settings=settings,
            scrapers=build_fixture_scrapers(),
        )

    monkeypatch.setattr(scrape_routes, "ScrapeService", _factory)
    monkeypatch.setattr(pipeline_routes, "ScrapeService", _factory)

    class _StubBrowserTool:
        def run(
            self, *, application_id: str, job_url: str, ats_provider: str, screenshot_urls: list[str]
        ) -> BrowserApplyResult:
            return BrowserApplyResult(
                status="success",
                confirmation_url=f"{job_url}/submitted",
                confirmation_number=f"CONF-{application_id[:8].upper()}",
            )

    monkeypatch.setattr(AutoApplyService, "_build_browser_tool", lambda self: _StubBrowserTool())
    yield
