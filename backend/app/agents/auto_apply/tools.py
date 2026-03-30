from __future__ import annotations

from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import random
import re
from typing import Any, Iterator

import structlog

from app.agents.auto_apply.ats.base import BrowserApplyResult
from app.agents.auto_apply.ats.detector import strategy_for_provider
from app.core.logging_safety import log_debug


logger = structlog.get_logger(__name__)


class PlaywrightUnavailableError(RuntimeError):
    pass


class PlaywrightApplyTool:
    _CAPTCHA_SELECTORS = [
        "iframe[src*='recaptcha']",
        "iframe[src*='hcaptcha']",
        ".g-recaptcha",
        ".h-captcha",
        "[data-sitekey]",
        "#cf-challenge-running",
        ".cf-turnstile",
        "input[name='cf-turnstile-response']",
    ]
    _CAPTCHA_TEXT_MARKERS = (
        "captcha",
        "recaptcha",
        "hcaptcha",
        "verify you are human",
        "cloudflare",
        "attention required",
    )
    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    ]

    def __init__(self, *, artifact_root_env: str = "AUTO_APPLY_ARTIFACT_ROOT") -> None:
        self._artifact_root_env = artifact_root_env
        self._runtime = None
        self._stealth_sync = None

    def run(
        self,
        *,
        application_id: str,
        job_url: str,
        ats_provider: str,
        screenshot_urls: list[str],
    ) -> BrowserApplyResult:
        strategy = strategy_for_provider(ats_provider)
        with self._playwright_session() as playwright:
            with self.browser_context(playwright) as (_, context):
                page = self.stealth_page(context)
                return strategy.apply(
                    page=page,
                    tool=self,
                    application_id=application_id,
                    job_url=job_url,
                    screenshot_urls=screenshot_urls,
                )

    @contextmanager
    def _playwright_session(self) -> Iterator[Any]:
        sync_playwright = self._load_runtime()
        with sync_playwright() as playwright:
            yield playwright

    def _load_runtime(self):
        if self._runtime is not None:
            return self._runtime
        try:
            sync_api = importlib.import_module("playwright.sync_api")
            self._runtime = getattr(sync_api, "sync_playwright")
            try:
                stealth_module = importlib.import_module("playwright_stealth")
                self._stealth_sync = getattr(stealth_module, "stealth_sync", None)
            except Exception:
                self._stealth_sync = None
            return self._runtime
        except Exception as error:
            raise PlaywrightUnavailableError("Playwright is not installed in this runtime.") from error

    @contextmanager
    def browser_context(self, playwright: Any) -> Iterator[tuple[Any, Any]]:
        browser = playwright.chromium.launch(headless=self._browser_should_be_headless())
        viewport = {
            "width": random.randint(1280, 1920),
            "height": random.randint(800, 1080),
        }
        context = browser.new_context(
            viewport=viewport,
            user_agent=random.choice(self._USER_AGENTS),
            locale="en-US",
        )
        try:
            yield browser, context
        finally:
            try:
                context.close()
            finally:
                browser.close()

    def stealth_page(self, context: Any) -> Any:
        page = context.new_page()
        if self._stealth_sync is not None:
            try:
                self._stealth_sync(page)
            except Exception as error:
                log_debug(logger, "auto_apply.browser.stealth_failed", error=str(error))
        return page

    def first_visible_selector(self, page: Any, selectors: list[str]) -> str | None:
        for selector in selectors:
            try:
                if page.locator(selector).count() > 0:
                    return selector
            except Exception:
                continue
        return None

    def human_click(self, page: Any, selector: str, *, timeout: int = 2500) -> bool:
        locator = page.locator(selector).first
        try:
            box = locator.bounding_box()
            if box is not None:
                target_x = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
                target_y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)
                page.mouse.move(target_x, target_y, steps=random.randint(8, 18))
            locator.click(timeout=timeout)
            return True
        except Exception as error:
            log_debug(logger, "auto_apply.browser.click_failed", selector=selector, error=str(error))
            return False

    def human_type(self, page: Any, selector: str, text: str) -> bool:
        locator = page.locator(selector).first
        try:
            locator.click(timeout=2500)
            locator.fill("")
            for character in text:
                locator.type(character, delay=random.randint(50, 150))
            return True
        except Exception as error:
            log_debug(logger, "auto_apply.browser.type_failed", selector=selector, error=str(error))
            return False

    def capture_screenshot(self, page: Any, destination: str) -> None:
        try:
            artifact_path = self._artifact_file_path(destination)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(artifact_path), full_page=True)
            log_debug(logger, "auto_apply.browser.screenshot_saved", destination=str(artifact_path))
        except Exception as error:
            log_debug(logger, "auto_apply.browser.screenshot_failed", destination=destination, error=str(error))

    def detect_captcha(self, page: Any) -> bool:
        try:
            content = page.content().lower()
        except Exception:
            content = ""
        if any(marker in content for marker in self._CAPTCHA_TEXT_MARKERS):
            return True
        for selector in self._CAPTCHA_SELECTORS:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return False

    def confirmation_number_for(self, *, application_id: str, prefix: str) -> str:
        token = re.sub(r"[^A-Z0-9]", "", application_id.upper())[:8]
        return f"{prefix}-{token}"

    def _artifact_file_path(self, screenshot_url: str) -> Path:
        relative_path = screenshot_url.lstrip("/")
        artifact_root = os.getenv(self._artifact_root_env, ".")
        return Path(artifact_root) / relative_path

    def _browser_should_be_headless(self) -> bool:
        value = os.getenv("AUTO_APPLY_HEADLESS", "true")
        return value.strip().lower() in {"1", "true", "yes", "on"}
