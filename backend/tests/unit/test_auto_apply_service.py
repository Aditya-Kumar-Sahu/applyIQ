from __future__ import annotations

from app.agents.auto_apply.ats.base import BrowserApplyResult
from app.agents.auto_apply.tools import PlaywrightApplyTool
from app.models.application import Application
from app.models.job import Job
from app.services.auto_apply_service import AutoApplyService


def test_supported_ats_returns_success_with_audit_artifacts() -> None:
    service = AutoApplyService()
    application = Application(id="app-1", user_id="user-1", job_id="job-1", pipeline_run_id="run-1")
    job = Job(
        id="job-1",
        external_id="indeed-1",
        source="indeed",
        title="ML Engineer Platform 1",
        company_name="Company 1",
        company_domain="company1.example",
        location="Remote",
        is_remote=True,
        salary_min=2500000,
        salary_max=3500000,
        description_text="ML platform role",
        description_embedding=[0.1, 0.2, 0.3],
        apply_url="https://jobs.applyiq.dev/indeed/1",
    )

    result = service.apply(application=application, job=job, has_credentials=False)

    assert result.status == "success"
    assert result.ats_provider == "indeed_apply"
    assert result.is_demo is True
    assert result.confirmation_url is not None
    assert result.confirmation_number is not None
    assert result.confirmation_number.startswith("DEMO-")
    assert len(result.screenshot_urls) == 2
    assert result.manual_required_reason is None


def test_unsupported_or_captcha_paths_fall_back_to_manual_required() -> None:
    service = AutoApplyService()
    application = Application(id="app-2", user_id="user-1", job_id="job-2", pipeline_run_id="run-1")
    job = Job(
        id="job-2",
        external_id="direct-1",
        source="direct",
        title="ML Engineer",
        company_name="Company 2",
        company_domain="company2.example",
        location="Remote",
        is_remote=True,
        salary_min=2500000,
        salary_max=3500000,
        description_text="Direct application role",
        description_embedding=[0.2, 0.3, 0.4],
        apply_url="https://jobs.applyiq.dev/taleo/captcha/2",
    )

    result = service.apply(application=application, job=job, has_credentials=False)

    assert result.status == "manual_required"
    assert result.ats_provider == "taleo"
    assert result.is_demo is False
    assert result.confirmation_url is None
    assert result.manual_required_reason is not None
    assert "CAPTCHA" in result.manual_required_reason or "manual" in result.manual_required_reason.lower()


def test_browser_mode_uses_real_browser_tool_when_available(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_APPLY_USE_BROWSER", "true")
    monkeypatch.setenv("AUTO_APPLY_DEMO_MODE", "true")

    class StubBrowserTool:
        def run(self, *, application_id: str, job_url: str, ats_provider: str, screenshot_urls: list[str]) -> BrowserApplyResult:
            assert application_id == "app-3"
            assert ats_provider == "greenhouse"
            assert len(screenshot_urls) == 2
            return BrowserApplyResult(
                status="success",
                confirmation_url=f"{job_url}/submitted",
                confirmation_number="GREEN-APP3",
            )

    service = AutoApplyService()
    monkeypatch.setattr(service, "_build_browser_tool", lambda: StubBrowserTool())

    application = Application(id="app-3", user_id="user-1", job_id="job-3", pipeline_run_id="run-1")
    job = Job(
        id="job-3",
        external_id="greenhouse-1",
        source="direct",
        title="Platform Engineer",
        company_name="Company 3",
        company_domain="company3.example",
        location="Remote",
        is_remote=True,
        salary_min=2500000,
        salary_max=3500000,
        description_text="Greenhouse role",
        description_embedding=[0.1, 0.2, 0.3],
        apply_url="https://boards.greenhouse.io/applyiq/jobs/123",
    )

    result = service.apply(application=application, job=job, has_credentials=True)

    assert result.status == "success"
    assert result.is_demo is False
    assert result.ats_provider == "greenhouse"
    assert result.confirmation_number == "GREEN-APP3"


def test_playwright_tool_detects_captcha_selectors() -> None:
    class Locator:
        def __init__(self, count_value: int) -> None:
            self._count_value = count_value

        def count(self) -> int:
            return self._count_value

    class FakePage:
        url = "https://jobs.applyiq.dev/captcha"

        def content(self) -> str:
            return "<html><body>normal page</body></html>"

        def locator(self, selector: str):
            if selector == ".h-captcha":
                return Locator(1)
            return Locator(0)

    tool = PlaywrightApplyTool()
    assert tool.detect_captcha(FakePage()) is True
