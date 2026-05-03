from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from prometheus_client import Counter, Histogram

from app.core.config import Settings


# --- Custom Metrics ---
SCRAPER_REQUESTS_TOTAL = Counter(
    "scraper_requests_total",
    "Total number of scraper requests",
    ["source", "status"]
)

SCRAPER_DURATION_SECONDS = Histogram(
    "scraper_duration_seconds",
    "Time spent scraping jobs",
    ["source"],
    buckets=(1, 5, 10, 30, 60, 120, 300)
)

LLM_TOKEN_USAGE_TOTAL = Counter(
    "llm_token_usage_total",
    "Total number of tokens used per model",
    ["model", "type"] # type: prompt, completion
)
# ----------------------


def configure_observability(settings: Settings) -> None:
    # 1. Sentry
    if settings.sentry_dsn_backend:
        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment=settings.environment,
            release=settings.release_version,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            integrations=[FastApiIntegration()],
            send_default_pii=False,
        )
