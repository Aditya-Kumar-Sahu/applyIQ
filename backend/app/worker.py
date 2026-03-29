from __future__ import annotations

from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "applyiq",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    imports=(
        "app.tasks.scrape_task",
        "app.tasks.pipeline_task",
        "app.tasks.email_monitor_task",
    )
)
