from __future__ import annotations

from dataclasses import dataclass

from app.models.application import Application
from app.models.job import Job


@dataclass
class AutoApplyResult:
    status: str
    ats_provider: str
    confirmation_url: str | None
    confirmation_number: str | None
    screenshot_urls: list[str]
    failure_reason: str | None
    manual_required_reason: str | None


class AutoApplyService:
    def detect_ats(self, job: Job) -> str:
        apply_url = job.apply_url.lower()
        source = job.source.lower()

        if "greenhouse" in apply_url:
            return "greenhouse"
        if "lever" in apply_url:
            return "lever"
        if "workday" in apply_url:
            return "workday"
        if "smartrecruiters" in apply_url:
            return "smartrecruiters"
        if "linkedin" in apply_url or source == "linkedin":
            return "linkedin_easy_apply"
        if "indeed" in apply_url or source == "indeed":
            return "indeed_apply"
        if "icims" in apply_url:
            return "icims"
        if "taleo" in apply_url:
            return "taleo"
        return "direct_form"

    def apply(self, *, application: Application, job: Job, has_credentials: bool) -> AutoApplyResult:
        ats_provider = self.detect_ats(job)
        screenshot_urls = self._artifact_paths(application.id, ats_provider)
        apply_url = job.apply_url.lower()

        if "captcha" in apply_url or ats_provider in {"taleo"}:
            return AutoApplyResult(
                status="manual_required",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=None,
                manual_required_reason="CAPTCHA or unsupported ATS detected. Complete this application manually.",
            )

        if ats_provider in {"linkedin_easy_apply", "workday"} and not has_credentials:
            return AutoApplyResult(
                status="manual_required",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=None,
                manual_required_reason="Stored credentials are required before this site can be auto-applied safely.",
            )

        confirmation_number = f"APPLY-{application.id.split('-')[0].upper()}"
        return AutoApplyResult(
            status="success",
            ats_provider=ats_provider,
            confirmation_url=f"{job.apply_url.rstrip('/')}/confirmation",
            confirmation_number=confirmation_number,
            screenshot_urls=screenshot_urls,
            failure_reason=None,
            manual_required_reason=None,
        )

    def _artifact_paths(self, application_id: str, ats_provider: str) -> list[str]:
        return [
            f"/artifacts/{application_id}/{ats_provider}-before.png",
            f"/artifacts/{application_id}/{ats_provider}-after.png",
        ]
