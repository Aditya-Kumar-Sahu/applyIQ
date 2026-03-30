from __future__ import annotations

import os

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging


settings = get_settings()

configure_logging(
    log_level=settings.log_level,
    log_to_file=settings.log_to_file,
    log_dir=settings.log_dir,
    log_file_name=settings.log_file_name,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
)

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
    ),
    beat_schedule_filename=os.getenv("CELERY_BEAT_SCHEDULE_FILENAME", "/tmp/celerybeat-schedule"),
)
