from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class BrowserApplyResult:
    status: str
    confirmation_url: str | None = None
    confirmation_number: str | None = None
    failure_reason: str | None = None
    manual_required_reason: str | None = None


class BrowserPage(Protocol):
    url: str

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None: ...

    def content(self) -> str: ...

    def locator(self, selector: str): ...

    def wait_for_timeout(self, timeout: int) -> None: ...


class BrowserTool(Protocol):
    def capture_screenshot(self, page: BrowserPage, destination: str) -> None: ...

    def detect_captcha(self, page: BrowserPage) -> bool: ...

    def first_visible_selector(self, page: BrowserPage, selectors: list[str]) -> str | None: ...

    def human_click(self, page: BrowserPage, selector: str, *, timeout: int = 2500) -> bool: ...

    def confirmation_number_for(self, *, application_id: str, prefix: str) -> str: ...


class ATSStrategy(Protocol):
    provider_name: str

    def apply(
        self,
        *,
        page: BrowserPage,
        tool: BrowserTool,
        application_id: str,
        job_url: str,
        screenshot_urls: list[str],
    ) -> BrowserApplyResult: ...

