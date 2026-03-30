from __future__ import annotations

from app.agents.auto_apply.ats.base import ATSStrategy, BrowserApplyResult, BrowserPage, BrowserTool


class LeverATSStrategy(ATSStrategy):
    provider_name = "lever"
    _SUBMIT_SELECTORS = [
        "button[type='submit']",
        "button:has-text('Submit Application')",
        "button:has-text('Apply')",
        "input[type='submit']",
    ]
    _CONFIRMATION_MARKERS = ("application submitted", "thanks for applying", "thank you for applying")

    def apply(
        self,
        *,
        page: BrowserPage,
        tool: BrowserTool,
        application_id: str,
        job_url: str,
        screenshot_urls: list[str],
    ) -> BrowserApplyResult:
        page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
        tool.capture_screenshot(page, screenshot_urls[0])
        if tool.detect_captcha(page):
            tool.capture_screenshot(page, screenshot_urls[1])
            return BrowserApplyResult(
                status="manual_required",
                manual_required_reason="CAPTCHA detected during Lever automation. Manual completion is required.",
            )

        submit_selector = tool.first_visible_selector(page, self._SUBMIT_SELECTORS)
        if submit_selector:
            tool.human_click(page, submit_selector)
            page.wait_for_timeout(1200)

        tool.capture_screenshot(page, screenshot_urls[1])
        page_text = page.content().lower()
        if any(marker in page_text for marker in self._CONFIRMATION_MARKERS):
            return BrowserApplyResult(
                status="success",
                confirmation_url=page.url,
                confirmation_number=tool.confirmation_number_for(application_id=application_id, prefix="LEVER"),
            )

        return BrowserApplyResult(
            status="manual_required",
            manual_required_reason=(
                "Lever application loaded, but the form requires candidate data or review before submission."
            ),
        )

