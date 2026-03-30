from __future__ import annotations

from dataclasses import dataclass
import os
import re

import structlog

from app.agents.auto_apply.ats.base import BrowserApplyResult
from app.agents.auto_apply.tools import PlaywrightApplyTool, PlaywrightUnavailableError
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
    is_demo: bool


class AutoApplyService:
    _CLICK_SELECTORS = [
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
        "button:has-text('Apply')",
        "[data-test='easy-apply-button']",
        "a:has-text('Easy Apply')",
        "a:has-text('Apply now')",
    ]

    def __init__(
        self,
        *,
        browser_mode_env: str = "AUTO_APPLY_USE_BROWSER",
        demo_mode_env: str = "AUTO_APPLY_DEMO_MODE",
        artifact_root_env: str = "AUTO_APPLY_ARTIFACT_ROOT",
    ) -> None:
        self._browser_mode_env = browser_mode_env
        self._demo_mode_env = demo_mode_env
        self._artifact_root_env = artifact_root_env

    def detect_ats(self, job: Job) -> str:
        apply_url = job.apply_url.lower()
        source = job.source.lower()
        log_debug(logger, "auto_apply.detect_ats.start", job_id=job.id, source=source)

        if source == "linkedin":
            return "linkedin_easy_apply"
        if source == "indeed":
            return "indeed_apply"
        if "greenhouse" in apply_url:
            return "greenhouse"
        if "lever" in apply_url:
            return "lever"
        if "workday" in apply_url:
            return "workday"
        if "smartrecruiters" in apply_url:
            return "smartrecruiters"
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
        browser_mode_enabled = self._is_browser_mode_enabled()
        demo_mode_enabled = self._is_demo_mode_enabled()
        log_debug(
            logger,
            "auto_apply.apply.start",
            application_id=application.id,
            job_id=job.id,
            ats_provider=ats_provider,
            has_credentials=has_credentials,
            browser_mode_enabled=browser_mode_enabled,
            demo_mode_enabled=demo_mode_enabled,
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
                is_demo=False,
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
                is_demo=False,
            )

        if browser_mode_enabled:
            browser_result = self._run_browser_apply(
                application=application,
                job=job,
                ats_provider=ats_provider,
                screenshot_urls=screenshot_urls,
            )
            if browser_result is not None:
                return browser_result

        if not demo_mode_enabled:
            return AutoApplyResult(
                status="manual_required",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=None,
                manual_required_reason=(
                    "Live browser automation is disabled and demo mode is off. "
                    "No simulated application was submitted."
                ),
                is_demo=False,
            )

        logger.warning(
            "AUTO_APPLY_DEMO_MODE",
            application_id=application.id,
            job_id=job.id,
            message="AUTO_APPLY_DEMO_MODE: returning simulated result - no real application was submitted",
        )
        confirmation_number = f"DEMO-{application.id.split('-')[0].upper()}"
        return AutoApplyResult(
            status="success",
            ats_provider=ats_provider,
            confirmation_url=f"{job.apply_url.rstrip('/')}/demo-confirmation",
            confirmation_number=confirmation_number,
            screenshot_urls=screenshot_urls,
            failure_reason=None,
            manual_required_reason=None,
            is_demo=True,
        )

    def _run_browser_apply(
        self,
        *,
        application: Application,
        job: Job,
        ats_provider: str,
        screenshot_urls: list[str],
    ) -> AutoApplyResult | None:
        try:
            browser_tool = self._build_browser_tool()
            browser_result = browser_tool.run(
                application_id=application.id,
                job_url=job.apply_url,
                ats_provider=ats_provider,
                screenshot_urls=screenshot_urls,
            )
            return self._map_browser_result(browser_result=browser_result, ats_provider=ats_provider, screenshot_urls=screenshot_urls)
        except PlaywrightUnavailableError:
            log_debug(
                logger,
                "auto_apply.browser.unavailable",
                application_id=application.id,
                reason="playwright_not_installed",
            )
            return AutoApplyResult(
                status="manual_required",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=None,
                manual_required_reason="Browser automation is enabled but Playwright is not installed in this runtime.",
                is_demo=False,
            )
        except Exception as error:
            log_debug(
                logger,
                "auto_apply.browser.failed",
                application_id=application.id,
                error=str(error),
            )
            return AutoApplyResult(
                status="failed",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=f"Browser auto-apply failed: {error}",
                manual_required_reason=None,
                is_demo=False,
            )

    def _build_browser_tool(self) -> PlaywrightApplyTool:
        return PlaywrightApplyTool(artifact_root_env=self._artifact_root_env)

    def _map_browser_result(
        self,
        *,
        browser_result: BrowserApplyResult,
        ats_provider: str,
        screenshot_urls: list[str],
    ) -> AutoApplyResult:
        status = browser_result.status
        if status == "success":
            return AutoApplyResult(
                status="success",
                ats_provider=ats_provider,
                confirmation_url=browser_result.confirmation_url,
                confirmation_number=browser_result.confirmation_number,
                screenshot_urls=screenshot_urls,
                failure_reason=None,
                manual_required_reason=None,
                is_demo=False,
            )
        if status == "manual_required":
            return AutoApplyResult(
                status="manual_required",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=browser_result.failure_reason,
                manual_required_reason=browser_result.manual_required_reason,
                is_demo=False,
            )
        return AutoApplyResult(
            status="failed",
            ats_provider=ats_provider,
            confirmation_url=None,
            confirmation_number=None,
            screenshot_urls=screenshot_urls,
            failure_reason=browser_result.failure_reason or "Browser auto-apply failed",
            manual_required_reason=browser_result.manual_required_reason,
            is_demo=False,
        )

    def _artifact_paths(self, application_id: str, ats_provider: str) -> list[str]:
        safe_provider = re.sub(r"[^a-z0-9_-]", "-", ats_provider.lower())
        paths = [
            f"/artifacts/{application_id}/{safe_provider}-before.png",
            f"/artifacts/{application_id}/{safe_provider}-after.png",
        ]
        log_debug(
            logger,
            "auto_apply.artifact_paths",
            application_id=application_id,
            ats_provider=ats_provider,
            paths_count=len(paths),
        )
        return paths

    def _is_browser_mode_enabled(self) -> bool:
        value = os.getenv("PLAYWRIGHT_ENABLED", os.getenv(self._browser_mode_env, "false"))
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _is_demo_mode_enabled(self) -> bool:
        value = os.getenv(self._demo_mode_env, "true")
        return value.strip().lower() in {"1", "true", "yes", "on"}
