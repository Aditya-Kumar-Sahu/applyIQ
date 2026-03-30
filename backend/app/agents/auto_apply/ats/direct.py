from __future__ import annotations

from app.agents.auto_apply.ats.base import ATSStrategy, BrowserApplyResult, BrowserPage, BrowserTool


class DirectApplyStrategy(ATSStrategy):
    provider_name = "direct_form"
    _CLICK_SELECTORS = [
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
        "button:has-text('Apply')",
        "[data-test='easy-apply-button']",
        "a:has-text('Easy Apply')",
        "a:has-text('Apply now')",
        "a:has-text('Apply')",
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
                manual_required_reason="CAPTCHA detected during browser automation. Manual completion is required.",
            )

        selector = tool.first_visible_selector(page, self._CLICK_SELECTORS)
        clicked = False
        if selector:
            clicked = tool.human_click(page, selector)
            page.wait_for_timeout(1200)

        tool.capture_screenshot(page, screenshot_urls[1])
        page_text = page.content().lower()
        if clicked and any(marker in page_text for marker in self._CONFIRMATION_MARKERS):
            return BrowserApplyResult(
                status="success",
                confirmation_url=page.url,
                confirmation_number=tool.confirmation_number_for(application_id=application_id, prefix="APPLY"),
            )

        if clicked:
            return BrowserApplyResult(
                status="success",
                confirmation_url=page.url,
                confirmation_number=tool.confirmation_number_for(application_id=application_id, prefix="APPLY"),
            )

        return BrowserApplyResult(
            status="manual_required",
            manual_required_reason="No supported apply control was found during browser automation. Complete this application manually.",
        )

