from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.core.logging_safety import log_debug

from app.models.application import Application
from app.models.job import Job


logger = structlog.get_logger(__name__)


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
        log_debug(logger, "auto_apply.detect_ats.start", job_id=job.id, source=source)

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
            log_debug(logger, "auto_apply.detect_ats.result", job_id=job.id, ats_provider="taleo")
            return "taleo"
        log_debug(logger, "auto_apply.detect_ats.result", job_id=job.id, ats_provider="direct_form")
        return "direct_form"

    def apply(self, *, application: Application, job: Job, has_credentials: bool) -> AutoApplyResult:
        ats_provider = self.detect_ats(job)
        screenshot_urls = self._artifact_paths(application.id, ats_provider)
        apply_url = job.apply_url.lower()
        log_debug(
            logger,
            "auto_apply.apply.start",
            application_id=application.id,
            job_id=job.id,
            ats_provider=ats_provider,
            has_credentials=has_credentials,
        )

        if "captcha" in apply_url or ats_provider in {"taleo"}:
            log_debug(
                logger,
                "auto_apply.apply.manual_required",
                application_id=application.id,
                reason="captcha_or_unsupported_ats",
            )
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
            log_debug(
                logger,
                "auto_apply.apply.manual_required",
                application_id=application.id,
                reason="missing_credentials",
            )
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
        log_debug(
            logger,
            "auto_apply.apply.success",
            application_id=application.id,
            ats_provider=ats_provider,
        )
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
        paths = [
            f"/artifacts/{application_id}/{ats_provider}-before.png",
            f"/artifacts/{application_id}/{ats_provider}-after.png",
        ]
        log_debug(
            logger,
            "auto_apply.artifact_paths",
            application_id=application_id,
            ats_provider=ats_provider,
            paths_count=len(paths),
        )
        return paths
