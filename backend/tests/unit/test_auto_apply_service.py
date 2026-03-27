from __future__ import annotations

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
    assert result.confirmation_url is not None
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
    assert result.confirmation_url is None
    assert result.manual_required_reason is not None
    assert "CAPTCHA" in result.manual_required_reason or "manual" in result.manual_required_reason.lower()
