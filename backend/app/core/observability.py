from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import Settings


def configure_observability(settings: Settings) -> None:
    if not settings.sentry_dsn_backend:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn_backend,
        environment=settings.environment,
        release=settings.release_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        integrations=[FastApiIntegration()],
        send_default_pii=False,
    )
