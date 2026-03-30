from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import os
import re
from typing import Any

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
    _CLICK_SELECTORS = [
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
        "button:has-text('Apply')",
        "[data-test='easy-apply-button']",
        "a:has-text('Easy Apply')",
        "a:has-text('Apply now')",
    ]

    def __init__(self, *, browser_mode_env: str = "AUTO_APPLY_USE_BROWSER", artifact_root_env: str = "AUTO_APPLY_ARTIFACT_ROOT") -> None:
        self._browser_mode_env = browser_mode_env
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
        log_debug(
            logger,
            "auto_apply.apply.start",
            application_id=application.id,
            job_id=job.id,
            ats_provider=ats_provider,
            has_credentials=has_credentials,
            browser_mode_enabled=browser_mode_enabled,
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

        if browser_mode_enabled:
            browser_result = self._run_browser_apply(
                application=application,
                job=job,
                ats_provider=ats_provider,
                screenshot_urls=screenshot_urls,
            )
            if browser_result is not None:
                return browser_result

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

    def _run_browser_apply(
        self,
        *,
        application: Application,
        job: Job,
        ats_provider: str,
        screenshot_urls: list[str],
    ) -> AutoApplyResult | None:
        try:
            playwright_sync_api = importlib.import_module("playwright.sync_api")
            PlaywrightTimeoutError = getattr(playwright_sync_api, "TimeoutError")
            sync_playwright = getattr(playwright_sync_api, "sync_playwright")
        except Exception:
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
            )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(job.apply_url, wait_until="domcontentloaded", timeout=45000)
                self._capture_screenshot(page, screenshot_urls[0])

                page_text = page.content().lower()
                if "captcha" in page_text or "recaptcha" in page_text:
                    self._capture_screenshot(page, screenshot_urls[1])
                    browser.close()
                    return AutoApplyResult(
                        status="manual_required",
                        ats_provider=ats_provider,
                        confirmation_url=None,
                        confirmation_number=None,
                        screenshot_urls=screenshot_urls,
                        failure_reason=None,
                        manual_required_reason="CAPTCHA detected during browser automation. Manual completion is required.",
                    )

                clicked = False
                for selector in self._CLICK_SELECTORS:
                    locator = page.locator(selector)
                    if locator.count() == 0:
                        continue
                    locator.first.click(timeout=2500)
                    clicked = True
                    break

                if clicked:
                    page.wait_for_timeout(1200)
                self._capture_screenshot(page, screenshot_urls[1])
                browser.close()

                confirmation_number = f"APPLY-{application.id.split('-')[0].upper()}"
                return AutoApplyResult(
                    status="success" if clicked else "manual_required",
                    ats_provider=ats_provider,
                    confirmation_url=page.url if clicked else None,
                    confirmation_number=confirmation_number if clicked else None,
                    screenshot_urls=screenshot_urls,
                    failure_reason=None,
                    manual_required_reason=None
                    if clicked
                    else "No supported apply control was found during browser automation. Complete this application manually.",
                )
        except PlaywrightTimeoutError:
            return AutoApplyResult(
                status="manual_required",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=None,
                manual_required_reason="Timed out while loading the application form. Complete this application manually.",
            )
        except Exception as error:
            return AutoApplyResult(
                status="failed",
                ats_provider=ats_provider,
                confirmation_url=None,
                confirmation_number=None,
                screenshot_urls=screenshot_urls,
                failure_reason=f"Browser auto-apply failed: {error}",
                manual_required_reason=None,
            )

    def _capture_screenshot(self, page: Any, screenshot_url: str) -> None:
        try:
            destination = self._artifact_file_path(screenshot_url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(destination), full_page=True)
            log_debug(logger, "auto_apply.browser.screenshot_saved", destination=str(destination))
        except Exception as error:
            log_debug(logger, "auto_apply.browser.screenshot_failed", error=str(error))

    def _artifact_file_path(self, screenshot_url: str) -> Path:
        relative_path = screenshot_url.lstrip("/")
        artifact_root = os.getenv(self._artifact_root_env, ".")
        return Path(artifact_root) / relative_path

    def _is_browser_mode_enabled(self) -> bool:
        value = os.getenv(self._browser_mode_env, "false")
        return value.strip().lower() in {"1", "true", "yes", "on"}

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
