from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.observability import configure_observability

settings = get_settings()

configure_logging(
    log_level=settings.log_level,
    log_to_file=settings.log_to_file,
    log_dir=settings.log_dir,
    log_file_name=settings.log_file_name,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
)
configure_observability(settings)

celery_app = Celery(
    "applyiq",
    broker=settings.celery_broker_url.get_secret_value(),
    backend=settings.celery_result_backend.get_secret_value(),
)

celery_app.conf.update(
    imports=(
        "app.tasks.scrape_task",
        "app.tasks.pipeline_task",
        "app.tasks.email_monitor_task",
    ),
    beat_schedule_filename=os.getenv("CELERY_BEAT_SCHEDULE_FILENAME", "/tmp/celerybeat-schedule"),
    beat_schedule={
        "poll-gmail-every-4h": {
            "task": "applyiq.email-monitor.poll_all_users",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "sweep-stale-pipeline-runs": {
            "task": "applyiq.pipeline.sweep_stale",
            "schedule": crontab(minute=30, hour="*/6"),
        },
    },
)
