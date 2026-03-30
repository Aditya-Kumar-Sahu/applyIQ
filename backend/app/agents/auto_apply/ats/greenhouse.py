from __future__ import annotations

from app.agents.auto_apply.ats.base import ATSStrategy, BrowserApplyResult, BrowserPage, BrowserTool


class GreenhouseATSStrategy(ATSStrategy):
    provider_name = "greenhouse"
    _ENTRY_SELECTORS = [
        "a:has-text('Apply for this job')",
        "button:has-text('Apply for this job')",
        "a:has-text('Apply Now')",
        "button:has-text('Apply Now')",
    ]
    _SUBMIT_SELECTORS = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit Application')",
        "button:has-text('Submit')",
    ]
    _CONFIRMATION_MARKERS = ("application submitted", "thank you for applying", "thanks for applying")

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
                manual_required_reason="CAPTCHA detected during Greenhouse automation. Manual completion is required.",
            )

        selector = tool.first_visible_selector(page, self._ENTRY_SELECTORS)
        if selector:
            tool.human_click(page, selector)
            page.wait_for_timeout(900)

        if tool.detect_captcha(page):
            tool.capture_screenshot(page, screenshot_urls[1])
            return BrowserApplyResult(
                status="manual_required",
                manual_required_reason="CAPTCHA detected during Greenhouse automation. Manual completion is required.",
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
                confirmation_number=tool.confirmation_number_for(application_id=application_id, prefix="GREEN"),
            )

        return BrowserApplyResult(
            status="manual_required",
            manual_required_reason=(
                "Greenhouse application loaded, but the form requires candidate data or selectors "
                "that are not safe to infer automatically."
            ),
        )

